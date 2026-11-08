"""Ensure a minimal public network exists for the AHOS model instance.

Creates (idempotently) a VCN, an internet gateway, a default route to it and a
public subnet with SSH ingress. Writes the subnet id to ``network.json`` next to
this file. No other port is opened.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import oci

VCN_CIDR = "10.0.0.0/16"
SUBNET_CIDR = "10.0.1.0/24"


def main() -> int:
    config = oci.config.from_file()
    tenancy = config["tenancy"]
    network = oci.core.VirtualNetworkClient(config)

    vcns = network.list_vcns(tenancy).data
    vcn = vcns[0] if vcns else None
    if vcn is None:
        print("VCN oluşturuluyor…")
        vcn = network.create_vcn(
            oci.core.models.CreateVcnDetails(
                compartment_id=tenancy,
                cidr_block=VCN_CIDR,
                display_name="ahos-vcn",
                dns_label="ahos",
            )
        ).data
        oci.wait_until(
            network, network.get_vcn(vcn.id), "lifecycle_state", "AVAILABLE", max_wait_seconds=120
        )
    print("VCN:", vcn.id)

    gateways = network.list_internet_gateways(tenancy, vcn_id=vcn.id).data
    gateway = gateways[0] if gateways else None
    if gateway is None:
        print("Internet gateway oluşturuluyor…")
        gateway = network.create_internet_gateway(
            oci.core.models.CreateInternetGatewayDetails(
                compartment_id=tenancy,
                vcn_id=vcn.id,
                is_enabled=True,
                display_name="ahos-igw",
            )
        ).data

    rt = network.list_route_tables(tenancy, vcn_id=vcn.id).data[0]
    rules = [r for r in (rt.route_rules or []) if r.destination != "0.0.0.0/0"]
    rules.append(
        oci.core.models.RouteRule(
            destination="0.0.0.0/0", destination_type="CIDR_BLOCK", network_entity_id=gateway.id
        )
    )
    network.update_route_table(
        rt.id, oci.core.models.UpdateRouteTableDetails(route_rules=rules)
    )
    print("Route table güncellendi:", rt.id)

    subnets = network.list_subnets(tenancy, vcn_id=vcn.id).data
    public = [s for s in subnets if not s.prohibit_public_ip_on_vnic]
    subnet = public[0] if public else None
    if subnet is None:
        print("Subnet oluşturuluyor…")
        subnet = network.create_subnet(
            oci.core.models.CreateSubnetDetails(
                compartment_id=tenancy,
                vcn_id=vcn.id,
                cidr_block=SUBNET_CIDR,
                display_name="ahos-subnet",
                prohibit_public_ip_on_vnic=False,
                route_table_id=rt.id,
            )
        ).data
        oci.wait_until(
            network,
            network.get_subnet(subnet.id),
            "lifecycle_state",
            "AVAILABLE",
            max_wait_seconds=120,
        )
    print("SUBNET:", subnet.id)

    # SSH erişimi: varsayılan güvenlik listesine 22/tcp ekle (yalnız 22).
    sl = network.list_security_lists(tenancy, vcn_id=vcn.id).data[0]
    ingress = list(sl.ingress_security_rules or [])
    if not any(
        r.protocol == "6" and r.tcp_options and r.tcp_options.destination_port_range
        and r.tcp_options.destination_port_range.min == 22
        for r in ingress
    ):
        ingress.append(
            oci.core.models.IngressSecurityRule(
                protocol="6",
                source="0.0.0.0/0",
                tcp_options=oci.core.models.TcpOptions(
                    destination_port_range=oci.core.models.PortRange(min=22, max=22)
                ),
            )
        )
        network.update_security_list(
            sl.id, oci.core.models.UpdateSecurityListDetails(ingress_security_rules=ingress)
        )
        print("SSH (22) girişi eklendi")

    record = {"vcn_id": vcn.id, "subnet_id": subnet.id, "gateway_id": gateway.id}
    (Path(__file__).resolve().parent / "network.json").write_text(
        json.dumps(record, indent=2), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
