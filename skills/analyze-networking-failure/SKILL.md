# Analyze Networking Failure

Deep analysis of AAP2 job failures caused by network connectivity issues.

## Workflow

1. **Read** the full incident context: stdout, events, job metadata
2. **Identify** the networking layer involved:
   - DNS: resolution failures, NXDOMAIN, timeout, wrong resolver
   - SSH: connection timeout, key rejected, port closed, host key verification failed
   - TLS/SSL: certificate expired, untrusted CA, hostname mismatch, protocol version
   - Proxy: proxy authentication failed, proxy unreachable, CONNECT tunnel failure
   - Routing: host unreachable, no route to host, network unreachable
   - Firewall: connection refused on specific ports, ICMP blocked
3. **Determine root cause** — is this a client-side config issue, server-side, or infrastructure?
4. **Assess risk and confidence** based on evidence
5. **Recommend** specific actions:
   - For DNS: check resolv.conf, dig/nslookup commands, DNS server config
   - For SSH: ssh-keygen commands, known_hosts fixes, firewall port checks
   - For TLS: certificate inspection commands, CA bundle updates
   - For proxy: proxy environment variable corrections, proxy config
   - For routing/firewall: ip route commands, firewall-cmd/iptables rules
6. **List** affected hosts and network paths from the output
