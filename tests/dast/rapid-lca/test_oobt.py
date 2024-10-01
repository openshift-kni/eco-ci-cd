import os
import subprocess
import random

import subprocess
import re

RAPIDAST_IMAGE = "quay.io/redhatproductsecurity/rapidast:2.5.0"

def test_oobt_basic():
    # 1. place kubeconfig in the TEST_DATA_DIR directory

    TEST_DATA_DIR = "oobt_test_data"

    port = random.randint(10000, 30000)

    # prep for testing
    os.system(f"chmod 666 {TEST_DATA_DIR}/kubeconfig")
    # Run the command and capture stdout
    command = f"podman run -it --rm -v ./{TEST_DATA_DIR}/kubeconfig:/home/rapidast/.kube/config:Z -v ./results:/opt/rapidast/results:Z -v $PWD:/test:Z -p {port}:{port} {RAPIDAST_IMAGE} rapidast.py --config /test/rapidast_runtime_cfg.yaml"

    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    stdout, stderr = process.communicate()

#    print(stdout)
    print("test completed. See the results directory")

if __name__ == "__main__":
    test_oobt_basic()
