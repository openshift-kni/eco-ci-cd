import os
import subprocess
import random

import subprocess
import re


RAPIDAST_IMAGE = "quay.io/redhatproductsecurity/rapidast:2.5.0"
def get_vpn_ip_address():
    try:
        ip_output = subprocess.check_output(['ip', 'addr']).decode('utf-8')
        # Use regular expression to extract IP addresses
        ip_addresses = re.findall(r'10.64.\d+\.\d+', ip_output)

		# Currently return the first IP address
		# TODO: fix if there are multiple IP addresses and it causes an issue

        return ip_addresses[0]
    except subprocess.CalledProcessError as e:
        return f"Error: {e}"

def test_oobt_basic():
    # 1. place kubeconfig in the TEST_DATA_DIR directory

    TEST_DATA_DIR = "oobt_test_data"
    RAPIDAST_CFG_FILE = "v5-none-oobt-template.yaml"

    port = random.randint(10000, 30000)
    ipaddr = get_vpn_ip_address()

    # create a rapidast config
    sed_cmd = f"sed 's/-p <port> -i <ipaddr>/-p {port} -i {ipaddr}/' {TEST_DATA_DIR}/{RAPIDAST_CFG_FILE} > rapidast_runtime_cfg.yaml"
    os.system(sed_cmd)
    
    # prep for testing
    os.system(f"chmod 666 {TEST_DATA_DIR}/kubeconfig")
    if not os.path.exists("results"):
        os.makedirs("results")
        os.system("podman unshare chown 1000 results")

    # Run the command and capture stdout
    command = f"podman run -it --rm -v ./{TEST_DATA_DIR}/kubeconfig:/home/rapidast/.kube/config:Z -v ./results:/opt/rapidast/results:Z -v $PWD:/test:Z -p {port}:{port} {RAPIDAST_IMAGE} rapidast.py --config /test/rapidast_runtime_cfg.yaml"
    print(command)

    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    stdout, stderr = process.communicate()
#    print(stdout)
    print("test completed. See the results directory")

if __name__ == "__main__":
    test_oobt_basic()
