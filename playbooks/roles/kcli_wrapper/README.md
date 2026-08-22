Role Name
=========

The goal of this role is to facilitate the use of the kcli tool through ansible.

Requirements
------------

In order to use this role, it is necessary that both [_libvirt_](https://libvirt.org/) and [_kcli_](https://kcli.readthedocs.io/en/latest/) are preinstalled on the target system.

To facilitate compliance with this requirement, just set the role variable `kcli_wrp_install_depencencies` variable and ansible will be in charge of checking and installing these dependencies. By default **no dependencies will be installed**.

> **Note**: Only available for _Fedora_, _RHEL_ and _CentOS_.

Role Variables
--------------

| Role Variable | Extra Fields |  Description | Default value |
|---------------|--------------|--------------|---------------|
| kcli_wrp_install_depencencies | None | If you want that the role try to install KCLI dependencies (Fedora, RHEL or CentOS should be supported by now), set to true | false |
| kcli_wrp_ssh_key | filename<br>size | When defined, autogenerate a pair of SSH both public and private keys to be used during cluster deployment. | None |
| kcli_wrp_libvirt | pool | Set the default kcli_wrp_libvirt pool to use.<br>Clean mode:<br>If `also_default` is `false`, the default pool won't be removed upon running with `--tags rollback`.<br>If `remove_files` is `false`, files that belongs to a pool won't be removed upon running with `--tags rollback` |`kcli_wrp_libvirt:`<br>&nbsp;&nbsp;&nbsp;&nbsp;`pool`:<br>&nbsp;&nbsp;&nbsp;&nbsp;`path`:<br>&nbsp;&nbsp;&nbsp;&nbsp;`clean_mode`:<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`also_default`:&nbsp;false<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`remove_files`:&nbsp;false|
| kcli | networks<br>clusters | Add `kcli` networks and clusters parameters to be passed through kcli command tool<br>The comprehensive list of values can be found here: https://kcli.readthedocs.io/en/latest/<br>KCLI Slack channel: https://kubernetes.slack.com/archives/CU76B52JE| None |
| kcli_wrp_oc | url<br>dest | Install both `oc` and `kubectl` tools if they are not already installed| None |
| kcli_wrp_dnsmasq | use_nm_plugin<br>drop_in_files | When defined, it generate dnsmasq drop-in file to be used along with the default dnsmasq instance running in the host machine<br>See some examples [here](https://docs.fedoraproject.org/en-US/fedora-server/administration/dnsmasq/) | None |

> **Note**: See [defaults.yml](defaults/main.yml) for futher details and examples

Results
------------

If `kcli_wrp_credentials` is defined:

    # NOTE: Do not change these default values
    # These are the path for the KCLI to store credentials:
    kcli_wrp_credentials:
      clusters_details: ~/.kcli/clusters
      kubeconfig: auth/kubeconfig
      kubeadmin_password: auth/kubeadmin-password

These files are read after cluster deployment is done and store as `ansible_facts` into the following variables to be used by next playbooks:

    kcli_wrp_credentials:
      <cluster_name_0>:
        kubeconfig: ...
        b64_kubeconfig: ...
        kubeadmin_password: ...
      ...
      <cluster_name_N>:
        kubeconfig: ...
        b64_kubeconfig: ...
        kubeadmin_password: ...

Dependencies
------------

Required Extra Galaxy roles:

```
 ---
 collections:
   - ansible.posix
   - community.crypto
```

Example Playbook
----------------

Including an example of how to use your role (for instance, with variables passed in as parameters) is always nice for users too:

    - name: Role Example Use
      hosts:
        - all
      gather_facts: false
      roles:
        - role: kcli_wrapper
          vars:
            kcli_wrp_install_depencencies: true
            kcli_wrp_ssh_key:
              filename: ~/.ssh/id_rsa_for_my_cluster
              size: 2048
            kcli_wrp_libvirt:
              pool:
                name: my_pool
                path: /opt/libvirt/images
            kcli_wrp:
              networks:
                - name: my-net
                  type: network
                  domain: example.lab
                  cidr: 172.16.33.0/24
                  secondary_cidr: fc00:52:0:1305::0/64
                  gateway: 172.16.33.1
                - name: my-br-net
                  bridge: true
                  bridgename: virbr0
                - name: my-macvtap-net
                  macvtap: true
                  nic: eth0
              clusters:
              # For example, if you want to install an openshift cluster
              # then use only parameters that make sense for the below command:
              # kcli create cluster openshift --paramfile=parameters.yml
              - type: openshift
                # kcli create cluster openshift --force --paramfile=parameters.yml
                force_installation: false
                parameters:
                    cluster: my-ocp
                    version: stable
                    tag: 4.14
                    domain: example.lab
                    pool: my_pool
                    nets:
                      - my-net
                      - my-br-net
                      - my-macvtap-net
                    keys:
                      - ~/.ssh/id_rsa_for_my_cluster.pub
                    ctlplanes: 3
                    workers: 0
                    memory: 16384
                    numcpus: 4
                    disk_size: 30
                    # IMPORTANT:
                    # If you decided to set you pull_secret file
                    # as base64 string using 'base64_pull_secret'
                    # parameter, it will take precedent over
                    # 'pull_secret' paramater.
                    # Note that 'base64_pull_secret' parameter is
                    # not part of KCLI
                    base64_pull_secret: null
                    pull_secret: ~/.docker/config.json
                    apps:
                      - local-storage-operator
                      - openshift-gitops-operator
                      - advanced-cluster-management
                      - topology-aware-lifecycle-manager
            kcli_wrp_oc:
              url: https://mirror.openshift.com/pub/openshift-v4/clients/ocp/stable/openshift-client-linux.tar.gz
              dest: /usr/bin
            kcli_wrp_dnsmasq:
              - path: /etc/NetworkManager/dnsmasq.d/99-example.lab.conf
                content: |
                  local=/example.lab/
                  # The below defines a Wildcard DNS Entry.
                  address=/.example.lab/192.168.44.44
                  # Below I define some host names.  I also pull in
                  address=/openshift.example.lab/192.168.44.120
                  address=/openshift-int.example.lab/192.168.44.120

License
-------

BSD

Author Information
------------------

Not much to tell [:)](https://www.linkedin.com/in/carlos-cardeñosa-a6882a14/)
