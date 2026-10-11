#define _POSIX_C_SOURCE 200809L
#include <openssl/ssl.h>
#include <openssl/err.h>
#include <openssl/x509.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <stdint.h>

/* A memory-BIO TLS fixture, never a network service or production TLS wrapper. */
static void check(int ok, const char *msg) {
    if (!ok) { fprintf(stderr, "%s\n", msg); ERR_print_errors_fp(stderr); exit(1); }
}
static double now(void) {
    struct timespec t; check(clock_gettime(CLOCK_MONOTONIC, &t)==0,"clock");
    return (double)t.tv_sec + (double)t.tv_nsec/1e9;
}
typedef struct { SSL_CTX *cc, *sc; SSL *c, *s; } Pair;
static size_t pump(SSL *from, SSL *to, size_t cap, int inspect, size_t *records) {
    unsigned char buf[1048576+65536];
    int n= BIO_read(SSL_get_wbio(from),buf,sizeof(buf));
    if (n<=0) return 0;
    if (inspect) {
        size_t p=0;
        while (p<(size_t)n) {
            check((size_t)n-p>=5,"truncated header");
            size_t len=((size_t)buf[p+3]<<8)|buf[p+4];
            check(buf[p]==23 && buf[p+1]==3 && buf[p+2]==3,"TLS1.3 header");
            check(len>=17 && len<=cap+17 && p+5+len<=(size_t)n,"record length");
            (*records)++; p+=5+len;
        }
    }
    check(BIO_write(SSL_get_rbio(to),buf,n)==n,"pump write");
    return (size_t)n;
}
static Pair pair_new(size_t cap) {
    Pair p={0};
    p.cc=SSL_CTX_new(TLS_client_method()); p.sc=SSL_CTX_new(TLS_server_method());
    check(p.cc && p.sc,"ctx");
    SSL_CTX *contexts[]={p.cc,p.sc};
    for (size_t i=0;i<2;i++) {
        check(SSL_CTX_set_min_proto_version(contexts[i],TLS1_3_VERSION)==1,"min TLS");
        check(SSL_CTX_set_max_proto_version(contexts[i],TLS1_3_VERSION)==1,"max TLS");
        check(SSL_CTX_set_ciphersuites(contexts[i],"TLS_AES_128_GCM_SHA256")==1,"cipher");
    }
    check(SSL_CTX_set_num_tickets(p.sc,0)==1,"tickets");
    EVP_PKEY *key=EVP_PKEY_Q_keygen(NULL,NULL,"EC","prime256v1"); check(key!=NULL,"key");
    X509 *cert=X509_new(); check(cert!=NULL,"cert");
    check(X509_set_version(cert,2)==1,"version");
    check(ASN1_INTEGER_set(X509_get_serialNumber(cert),1)==1,"serial");
    check(X509_gmtime_adj(X509_getm_notBefore(cert),-60)!=NULL,"notBefore");
    check(X509_gmtime_adj(X509_getm_notAfter(cert),3600)!=NULL,"notAfter");
    check(X509_set_pubkey(cert,key)==1,"pubkey");
    X509_NAME *name=X509_get_subject_name(cert);
    check(X509_NAME_add_entry_by_txt(name,"CN",MBSTRING_ASC,(unsigned char*)"local-fixture",-1,-1,0)==1,"CN");
    check(X509_set_issuer_name(cert,name)==1 && X509_sign(cert,key,EVP_sha256())>0,"sign");
    check(SSL_CTX_use_certificate(p.sc,cert)==1 && SSL_CTX_use_PrivateKey(p.sc,key)==1,"server key");
    check(X509_STORE_add_cert(SSL_CTX_get_cert_store(p.cc),cert)==1,"fixture trust");
    SSL_CTX_set_verify(p.cc,SSL_VERIFY_PEER,NULL);
    X509_free(cert); EVP_PKEY_free(key);
    p.c=SSL_new(p.cc); p.s=SSL_new(p.sc); check(p.c && p.s,"SSL");
    SSL_set_bio(p.c,BIO_new(BIO_s_mem()),BIO_new(BIO_s_mem()));
    SSL_set_bio(p.s,BIO_new(BIO_s_mem()),BIO_new(BIO_s_mem()));
    check(SSL_get_rbio(p.c)&&SSL_get_wbio(p.c)&&SSL_get_rbio(p.s)&&SSL_get_wbio(p.s),"BIO");
    check(SSL_set1_host(p.c,"local-fixture")==1,"fixture hostname");
    SSL_set_connect_state(p.c); SSL_set_accept_state(p.s);
    check(SSL_set_max_send_fragment(p.s,cap)==1,"fragment cap");
    for (int i=0;i<20 && (!SSL_is_init_finished(p.c)||!SSL_is_init_finished(p.s));i++) {
        SSL *peers[]={p.c,p.s};
        for (int j=0;j<2;j++) {
            if (!SSL_is_init_finished(peers[j])) {
                int r=SSL_do_handshake(peers[j]);
                int e=r==1?SSL_ERROR_NONE:SSL_get_error(peers[j],r);
                check(e==SSL_ERROR_NONE||e==SSL_ERROR_WANT_READ||e==SSL_ERROR_WANT_WRITE,"handshake");
            }
            (void)pump(peers[j],peers[1-j],0,0,NULL);
        }
    }
    check(SSL_is_init_finished(p.c)&&SSL_is_init_finished(p.s),"handshake bounded");
    check(SSL_get_verify_result(p.c)==X509_V_OK,"verify");
    check(strcmp(SSL_get_cipher_name(p.c),"TLS_AES_128_GCM_SHA256")==0,"negotiated cipher");
    return p;
}
static void pair_free(Pair *p) { SSL_free(p->c);SSL_free(p->s);SSL_CTX_free(p->cc);SSL_CTX_free(p->sc); }
static size_t send_response(Pair *p,const unsigned char *input,unsigned char *output,
                            size_t len,size_t write_size,size_t cap,int oracle,size_t *records) {
    size_t wire=0, sent=0, received=0;
    while(sent<len) {
        size_t n=len-sent; if(n>write_size)n=write_size;
        size_t used=0;check(SSL_write_ex(p->s,input+sent,n,&used)==1 && used==n,"write");sent+=n;
        wire+=pump(p->s,p->c,cap,oracle,records);
        while(received<sent) {
            size_t got=0;check(SSL_read_ex(p->c,output+received,len-received,&got)==1 && got>0,"read");received+=got;
        }
    }
    check(received==len,"byte count");
    if(oracle)check(memcmp(input,output,len)==0,"independent byte oracle");
    return wire;
}
static void negative_test(int corrupt) {
    Pair p=pair_new(1024);unsigned char in[128]={7},wire[1024],out[128];size_t n=0,got=0;
    check(SSL_write_ex(p.s,in,sizeof(in),&n)==1 && n==sizeof(in),"negative write");
    int w=BIO_read(SSL_get_wbio(p.s),wire,sizeof(wire));check(w==150,"negative wire length");
    if(corrupt)wire[w-1]^=1;
    int first=corrupt?w:w-1;
    check(BIO_write(SSL_get_rbio(p.c),wire,first)==first,"negative feed");
    int r=SSL_read_ex(p.c,out,sizeof(out),&got);int e=SSL_get_error(p.c,r);
    check(r==0 && got==0 && e==(corrupt?SSL_ERROR_SSL:SSL_ERROR_WANT_READ),"no unauthenticated release");
    if(!corrupt) {
        check(BIO_write(SSL_get_rbio(p.c),wire+w-1,1)==1,"last byte");
        check(SSL_read_ex(p.c,out,sizeof(out),&got)==1 && got==sizeof(in) && memcmp(in,out,got)==0,"completed release");
    }
    ERR_clear_error();pair_free(&p);
}
static size_t number(const char *s) { char *end=NULL; unsigned long long n=strtoull(s,&end,10);check(s[0]!='-' && end && *end==0 && n>0 && n<=1073741824ULL,"positive bounded integer");return(size_t)n; }
int main(int argc,char **argv) {
    check(argc==5,"usage: probe CAP LENGTH WRITE_SIZE REPEATS");
    size_t cap=number(argv[1]),len=number(argv[2]),write_size=number(argv[3]),reps=number(argv[4]);
    check((cap==1024||cap==4096||cap==16384)&&len<=1048576&&write_size<=1048576&&reps<=1000000,"bounds");
    negative_test(0);negative_test(1);
    unsigned char *input=malloc(len),*output=malloc(len);check(input&&output,"buffers");
    for(size_t i=0;i<len;i++)input[i]=(unsigned char)((i*131+17)%251);
    double setup_start=now();Pair p=pair_new(cap);double setup=now()-setup_start;
    size_t records=0,wire=send_response(&p,input,output,len,write_size,cap,1,&records);
    size_t expected=0;
    for(size_t i=0;i<len;i+=write_size) {size_t n=len-i;if(n>write_size)n=write_size;expected+=(n+cap-1)/cap;}
    check(records==expected && wire==len+22*expected,"independent framing oracle");
    for(int i=0;i<8;i++)(void)send_response(&p,input,output,len,write_size,cap,0,NULL);
    double begin=now();size_t total_wire=0;
    for(size_t i=0;i<reps;i++)total_wire+=send_response(&p,input,output,len,write_size,cap,0,NULL);
    double elapsed=now()-begin;
    check(total_wire==wire*reps && memcmp(input,output,len)==0,"final oracle");
    double drop_start=now();pair_free(&p);free(input);free(output);double drop=now()-drop_start;
    printf("{\"cap\":%zu,\"length\":%zu,\"write_size\":%zu,\"repeats\":%zu,\"records\":%zu,\"wire_bytes\":%zu,\"ns_per_response\":%.3f,\"setup_us\":%.3f,\"teardown_us\":%.3f,\"openssl\":\"%s\",\"correct\":true}\n",cap,len,write_size,reps,records,wire,elapsed*1e9/(double)reps,setup*1e6,drop*1e6,OpenSSL_version(OPENSSL_VERSION));
    return 0;
}
