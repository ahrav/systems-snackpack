# Primary sources

- [Agrawal et al., USENIX ATC 2008, Design Tradeoffs for SSD Performance](https://www.usenix.org/legacy/events/usenix08/tech/full_papers/agrawal/agrawal_html/index.html): sections 3.2/3.4 cleaning, reserve blocks, wear and persistence; historical geometry is not a current SSD specification.
- [Xiang and Kurkoski, 2011, An Improved Analytical Expression for Write Amplification in NAND Flash](https://arxiv.org/abs/1110.4245): uniform-random/greedy model assumptions and overprovisioning.
- [Frankie et al., 2012, Analysis of Trim Commands on Overprovisioning and Write Amplification in Solid State Drives](https://arxiv.org/abs/1208.1794): workload/Trim models.
- [NVMe Base 2.1, SMART / Health Information](https://nvmexpress.org/wp-content/uploads/NVM-Express-Base-Specification-Revision-2.1-2024.08.05-Ratified.pdf): Data Units Written is host traffic, rounded thousands of 512-byte units; raw zero means not reported.
- [util-linux fstrim manual](https://man7.org/linux/man-pages/man8/fstrim.8.html): reported potential-discard ranges are not physical erasure evidence.
- [NVM Express FDP overview](https://nvmexpress.org/nvmeflexible-data-placement-fdp-blog/): placement information can help group lifetimes; marketing claims are not performance guarantees.
- [Yang, Misra and Rubenstein, 2015](https://www.sigmetrics.org/mama/2015/abstracts/YYang.pdf): greedy optimality under independent identical-rate memoryless page lifetimes, not arbitrary traces.
- [Van Houdt, 2013, hot/cold data](https://win.uantwerpen.be/~vanhoudt/papers/2013/hot_cold.pdf): multi-frontier placement changes policy comparisons; not this single-frontier sample policy.

Accessed 2026-10-08. The conservation equation in this artifact is derived directly from its executable model. Physical hardware effects are unmeasured.
