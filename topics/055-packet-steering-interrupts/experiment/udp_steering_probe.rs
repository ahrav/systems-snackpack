//! Correctness-focused Linux UDP receive-placement probe.

#![deny(warnings)]

use std::collections::{BTreeMap, BTreeSet};
use std::env;
use std::io::{self, Write};
use std::net::{Ipv4Addr, SocketAddr, SocketAddrV4, UdpSocket};
use std::os::fd::AsRawFd;
use std::time::Duration;

const SOL_SOCKET: i32 = 1;
const SO_INCOMING_CPU: i32 = 49;
const SO_INCOMING_NAPI_ID: i32 = 56;
const MAGIC: u32 = 0x5354_5235;
const MESSAGE_BYTES: usize = 16;

unsafe extern "C" {
    fn getsockopt(
        fd: i32,
        level: i32,
        option_name: i32,
        option_value: *mut core::ffi::c_void,
        option_len: *mut u32,
    ) -> i32;
}

fn socket_i32(socket: &UdpSocket, option_name: i32) -> io::Result<i32> {
    let mut value = -1_i32;
    let mut length = size_of::<i32>() as u32;
    // SAFETY: both output pointers name writable objects of the advertised
    // sizes. The socket owns a live descriptor for this call.
    let result = unsafe {
        getsockopt(
            socket.as_raw_fd(),
            SOL_SOCKET,
            option_name,
            (&raw mut value).cast(),
            &raw mut length,
        )
    };
    if result != 0 {
        return Err(io::Error::last_os_error());
    }
    if length as usize != size_of::<i32>() {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "getsockopt returned an unexpected option length",
        ));
    }
    Ok(value)
}

fn message(flow: u32, sequence: u32) -> [u8; MESSAGE_BYTES] {
    let mut bytes = [0_u8; MESSAGE_BYTES];
    bytes[..4].copy_from_slice(&MAGIC.to_be_bytes());
    bytes[4..8].copy_from_slice(&flow.to_be_bytes());
    bytes[8..12].copy_from_slice(&sequence.to_be_bytes());
    bytes[12..].copy_from_slice(&(flow ^ sequence ^ MAGIC).to_be_bytes());
    bytes
}

fn parse_message(bytes: &[u8]) -> Result<(u32, u32), &'static str> {
    if bytes.len() != MESSAGE_BYTES {
        return Err("wrong datagram length");
    }
    let magic = u32::from_be_bytes(bytes[..4].try_into().expect("four-byte slice"));
    let flow = u32::from_be_bytes(bytes[4..8].try_into().expect("four-byte slice"));
    let sequence = u32::from_be_bytes(bytes[8..12].try_into().expect("four-byte slice"));
    let checksum = u32::from_be_bytes(bytes[12..].try_into().expect("four-byte slice"));
    if magic != MAGIC || checksum != flow ^ sequence ^ MAGIC {
        return Err("wrong datagram magic or checksum");
    }
    Ok((flow, sequence))
}

#[derive(Default)]
struct FlowObservation {
    peers: BTreeSet<SocketAddr>,
    cpus: BTreeSet<i32>,
    napis: BTreeSet<i32>,
    pairs: BTreeSet<(i32, i32)>,
    packets: usize,
}

fn print_client_summary(
    flow_count: usize,
    packets_per_flow: usize,
    per_flow: &BTreeMap<u32, FlowObservation>,
    source_sha256: &str,
) {
    let peer_stable = per_flow
        .values()
        .filter(|value| value.peers.len() == 1)
        .count();
    let cpu_stable = per_flow
        .values()
        .filter(|value| value.cpus.len() == 1)
        .count();
    let napi_stable = per_flow
        .values()
        .filter(|value| value.napis.len() == 1)
        .count();
    let pair_stable = per_flow
        .values()
        .filter(|value| value.pairs.len() == 1)
        .count();
    let known_cpu_flows = per_flow
        .values()
        .filter(|value| !value.cpus.is_empty() && value.cpus.iter().all(|cpu| *cpu >= 0))
        .count();
    let positive_napi_flows = per_flow
        .values()
        .filter(|value| !value.napis.is_empty() && value.napis.iter().all(|napi| *napi > 0))
        .count();
    let cpus = per_flow
        .values()
        .flat_map(|value| value.cpus.iter().copied())
        .collect::<BTreeSet<_>>();
    let napis = per_flow
        .values()
        .flat_map(|value| value.napis.iter().copied())
        .collect::<BTreeSet<_>>();
    let positive_napis = napis.iter().copied().filter(|value| *value > 0).count();
    let observations = per_flow.values().map(|value| value.packets).sum::<usize>();

    for (flow, value) in per_flow {
        let peers = value
            .peers
            .iter()
            .map(ToString::to_string)
            .collect::<Vec<_>>()
            .join(",");
        let cpus = value
            .cpus
            .iter()
            .map(ToString::to_string)
            .collect::<Vec<_>>()
            .join(",");
        let napis = value
            .napis
            .iter()
            .map(ToString::to_string)
            .collect::<Vec<_>>()
            .join(",");
        println!(
            "flow role=client id={flow} peers={peers} cpus={cpus} napis={napis} packets={}",
            value.packets
        );
    }
    println!(
        "summary status=ok role=client placement_scope=connected_flow_socket flows={flow_count} packets_per_flow={packets_per_flow} observations={observations} peer_stable={peer_stable}/{flow_count} cpu_stable={cpu_stable}/{flow_count} napi_stable={napi_stable}/{flow_count} pair_stable={pair_stable}/{flow_count} known_cpu_flows={known_cpu_flows}/{flow_count} positive_napi_flows={positive_napi_flows}/{flow_count} unique_cpus={} unique_napi_ids={} positive_napi_ids={positive_napis} source_sha256={source_sha256}",
        cpus.len(),
        napis.len(),
    );
}

fn run_server(
    bind: SocketAddrV4,
    flow_count: usize,
    packets_per_flow: usize,
    source_sha256: &str,
) -> Result<(), Box<dyn std::error::Error>> {
    let total_packets = flow_count
        .checked_mul(packets_per_flow)
        .ok_or("packet count overflow")?;
    let socket = UdpSocket::bind(bind)?;
    socket.set_read_timeout(Some(Duration::from_secs(30)))?;
    println!(
        "ready role=server bind={bind} flows={flow_count} packets_per_flow={packets_per_flow} source_sha256={source_sha256}"
    );
    io::stdout().flush()?;

    let mut seen = BTreeSet::new();
    let mut per_flow = BTreeMap::<u32, FlowObservation>::new();
    for _ in 0..total_packets {
        let mut bytes = [0_u8; 64];
        let (length, peer) = socket.recv_from(&mut bytes)?;
        let (flow, sequence) = parse_message(&bytes[..length])?;
        if flow as usize >= flow_count
            || sequence as usize >= packets_per_flow
            || !seen.insert((flow, sequence))
        {
            return Err("duplicate or out-of-range datagram".into());
        }
        let observation = per_flow.entry(flow).or_default();
        observation.peers.insert(peer);
        observation.packets += 1;
        if socket.send_to(&bytes[..length], peer)? != length {
            return Err("short UDP echo".into());
        }
    }
    if per_flow.len() != flow_count
        || per_flow
            .values()
            .any(|value| value.packets != packets_per_flow || value.peers.len() != 1)
    {
        return Err("incomplete or unstable receive set".into());
    }
    let unique_peers = per_flow
        .values()
        .flat_map(|value| value.peers.iter())
        .collect::<BTreeSet<_>>()
        .len();
    if unique_peers != flow_count {
        return Err("client source endpoints were not unique".into());
    }
    let shared_cpu = socket_i32(&socket, SO_INCOMING_CPU)?;
    let shared_napi = socket_i32(&socket, SO_INCOMING_NAPI_ID)?;
    for (flow, observation) in &per_flow {
        let peer = observation
            .peers
            .iter()
            .next()
            .expect("validated nonempty peer set");
        println!(
            "flow role=server placement_scope=peer_identity_only id={flow} peer={peer} packets={}",
            observation.packets
        );
    }
    println!(
        "identity role=server live_flows={flow_count} unique_source_endpoints={unique_peers}/{flow_count}"
    );
    println!(
        "summary status=ok role=server placement_scope=shared_socket_only flows={flow_count} packets_per_flow={packets_per_flow} observations={total_packets} peer_stable={flow_count}/{flow_count} unique_source_endpoints={unique_peers}/{flow_count} shared_socket_cpu={shared_cpu} shared_socket_napi={shared_napi} source_sha256={source_sha256}"
    );
    Ok(())
}

fn run_client(
    destination: SocketAddrV4,
    flow_count: usize,
    packets_per_flow: usize,
    source_sha256: &str,
) -> Result<(), Box<dyn std::error::Error>> {
    let mut sockets = Vec::with_capacity(flow_count);
    let mut source_endpoints = BTreeSet::new();
    for _ in 0..flow_count {
        let socket = UdpSocket::bind((Ipv4Addr::UNSPECIFIED, 0))?;
        socket.set_read_timeout(Some(Duration::from_secs(5)))?;
        socket.connect(destination)?;
        if !source_endpoints.insert(socket.local_addr()?) {
            return Err("kernel reused a live client source endpoint".into());
        }
        sockets.push(socket);
    }
    if sockets.len() != flow_count || source_endpoints.len() != flow_count {
        return Err("not all client sockets are simultaneously live and unique".into());
    }
    println!(
        "start role=client destination={destination} flows={flow_count} packets_per_flow={packets_per_flow} source_sha256={source_sha256}"
    );

    let mut per_flow = BTreeMap::<u32, FlowObservation>::new();
    for (flow_index, socket) in sockets.iter().enumerate() {
        let flow = u32::try_from(flow_index)?;
        for sequence_index in 0..packets_per_flow {
            let sequence = u32::try_from(sequence_index)?;
            let bytes = message(flow, sequence);
            if socket.send(&bytes)? != bytes.len() {
                return Err("short UDP send".into());
            }
            let mut echo = [0_u8; 64];
            let length = socket.recv(&mut echo)?;
            if echo[..length] != bytes {
                return Err("echo mismatch".into());
            }
            let cpu = socket_i32(socket, SO_INCOMING_CPU)?;
            let napi = socket_i32(socket, SO_INCOMING_NAPI_ID)?;
            let observation = per_flow.entry(flow).or_default();
            observation.peers.insert(destination.into());
            observation.cpus.insert(cpu);
            observation.napis.insert(napi);
            observation.pairs.insert((cpu, napi));
            observation.packets += 1;
        }
    }
    println!(
        "identity role=client live_flows={flow_count} unique_source_endpoints={}/{flow_count}",
        source_endpoints.len()
    );
    print_client_summary(flow_count, packets_per_flow, &per_flow, source_sha256);
    Ok(())
}

fn parse_endpoint(ip: &str, port: &str) -> Result<SocketAddrV4, Box<dyn std::error::Error>> {
    let port: u16 = port.parse()?;
    if port == 0 {
        return Err("port must be nonzero".into());
    }
    Ok(SocketAddrV4::new(ip.parse()?, port))
}

fn valid_sha256(value: &str) -> bool {
    value.len() == 64
        && value
            .bytes()
            .all(|byte| byte.is_ascii_hexdigit() && !byte.is_ascii_uppercase())
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let arguments = env::args().collect::<Vec<_>>();
    if arguments.len() != 7 {
        return Err(
            "usage: udp_steering_probe <server|client> <IPv4> <port> <flows> <packets-per-flow> <source-sha256>"
                .into(),
        );
    }
    let endpoint = parse_endpoint(&arguments[2], &arguments[3])?;
    let flow_count: usize = arguments[4].parse()?;
    let packets_per_flow: usize = arguments[5].parse()?;
    let source_sha256 = &arguments[6];
    if flow_count == 0 || flow_count > 4096 {
        return Err("flows must be between 1 and 4096".into());
    }
    if packets_per_flow == 0 || packets_per_flow > 65_536 {
        return Err("packets-per-flow must be between 1 and 65536".into());
    }
    if flow_count
        .checked_mul(packets_per_flow)
        .is_none_or(|total| total > 1_048_576)
    {
        return Err("total packet count must not exceed 1048576".into());
    }
    if !valid_sha256(source_sha256) {
        return Err("source-sha256 must be 64 lowercase hexadecimal characters".into());
    }
    match arguments[1].as_str() {
        "server" => run_server(endpoint, flow_count, packets_per_flow, source_sha256),
        "client" => run_client(endpoint, flow_count, packets_per_flow, source_sha256),
        _ => Err("mode must be server or client".into()),
    }
}
