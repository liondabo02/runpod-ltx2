"""Create the free ARM instance for AHOS, retrying across availability domains.

Uses the OCI Python SDK (installed with oci-cli). Reads ~/.oci/config, picks the
first subnet in the region unless given, resolves the Ubuntu 24.04 aarch64 image
for the chosen shape, and launches with the given cloud-init user data.

    python ops/oracle/create_instance.py --ssh-pub ~/.ssh/ahos-quality-99.pub

Prints the instance OCID and public IP on success.
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
import time
from pathlib import Path

import oci


def first_subnet(network, compartment_id: str):
    vcns = network.list_vcns(compartment_id).data
    for vcn in vcns:
        subnets = network.list_subnets(compartment_id, vcn_id=vcn.id).data
        for subnet in subnets:
            if not subnet.prohibit_public_ip_on_vnic:
                return subnet
    raise SystemExit("Uygun (public IP'ye izinli) subnet bulunamadı.")


def ubuntu_image(compute, compartment_id: str, shape: str) -> str:
    images = compute.list_images(
        compartment_id,
        operating_system="Canonical Ubuntu",
        operating_system_version="24.04",
        shape=shape,
        sort_by="TIMECREATED",
        sort_order="DESC",
    ).data
    if not images:
        raise SystemExit("Ubuntu 24.04 imajı bulunamadı.")
    return images[0].id


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--compartment-id", default="")
    parser.add_argument("--subnet-id", default="")
    parser.add_argument(
        "--ssh-pub",
        default=str(Path.home() / ".ssh" / "ahos-quality-99" / "oracle_ed25519.pub"),
    )
    parser.add_argument(
        "--cloud-init",
        default=str(Path(__file__).resolve().parent / "cloud-init-ollama.yaml"),
    )
    parser.add_argument("--shape", default="VM.Standard.A1.Flex")
    parser.add_argument("--ocpus", type=int, default=2)
    parser.add_argument("--memory-gb", type=int, default=12)
    parser.add_argument("--interval", type=int, default=120)
    parser.add_argument("--max-hours", type=float, default=6.0)
    parser.add_argument("--display-name", default="AHOS-QUALITY-99")
    args = parser.parse_args()

    config = oci.config.from_file()
    tenancy = config["tenancy"]
    region = config.get("region", "?")
    identity = oci.identity.IdentityClient(config)
    compute = oci.core.ComputeClient(config)
    network = oci.core.VirtualNetworkClient(config)

    compartment_id = args.compartment_id or tenancy
    subnet_id = args.subnet_id or first_subnet(network, compartment_id).id
    ssh_key = Path(args.ssh_pub).read_text(encoding="utf-8").strip()
    user_data = base64.b64encode(Path(args.cloud_init).read_bytes()).decode()

    ads = [ad.name for ad in identity.list_availability_domains(tenancy).data]
    image_id = ubuntu_image(compute, compartment_id, args.shape)

    print(f"region={region} compartment={compartment_id} subnet={subnet_id}")
    print(f"shape={args.shape} {args.ocpus} OCPU / {args.memory_gb} GB · image={image_id}")
    print(f"availability domains: {ads}")

    deadline = time.time() + args.max_hours * 3600
    attempt = 0
    while time.time() < deadline:
        for ad in ads:
            attempt += 1
            details = oci.core.models.LaunchInstanceDetails(
                availability_domain=ad,
                compartment_id=compartment_id,
                shape=args.shape,
                shape_config=oci.core.models.LaunchInstanceShapeConfigDetails(
                    ocpus=args.ocpus, memory_in_gbs=args.memory_gb
                ),
                image_id=image_id,
                subnet_id=subnet_id,
                display_name=args.display_name,
                metadata={"ssh_authorized_keys": ssh_key, "user_data": user_data},
            )
            print(f"[{time.strftime('%H:%M:%S')}] deneme {attempt}: {ad}")
            try:
                response = compute.launch_instance(details)
                instance = response.data
                print("OLUŞTURULDU:", instance.id)
                public_ip = None
                attachments = compute.list_vnic_attachments(
                    compartment_id, instance_id=instance.id
                ).data
                for attachment in attachments:
                    vnic_data = network.get_vnic(attachment.vnic_id).data
                    if vnic_data.public_ip:
                        public_ip = vnic_data.public_ip
                        break
                record = {
                    "instance_id": instance.id,
                    "public_ip": public_ip,
                    "availability_domain": ad,
                    "region": region,
                    "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                }
                (Path(__file__).resolve().parent / "last-instance.json").write_text(
                    json.dumps(record, indent=2), encoding="utf-8"
                )
                print("PUBLIC_IP:", public_ip)
                return 0
            except oci.exceptions.ServiceError as exc:
                message = str(exc.message)
                if "capacity" in message.lower():
                    print(f"  kapasite yok: {message[:120]}")
                else:
                    print(f"  hata: {exc.code}: {message[:160]}")
        print(f"  {args.interval} sn bekleniyor…")
        time.sleep(args.interval)

    print("Süre doldu; örnek oluşturulamadı.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
