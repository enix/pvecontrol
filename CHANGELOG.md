# CHANGELOG


## v0.5.0 (2025-01-22)

### Bug Fixes

- Cleanup code
  ([`dd97cdc`](https://github.com/enix/pvecontrol/commit/dd97cdc18eddb2cbe9e07eb351933c3ee228b634))

- Correct clusterconfig default value overwrite
  ([`45fd3c2`](https://github.com/enix/pvecontrol/commit/45fd3c28c9dc813551bfc35b8a5d20cb8dc9ea6f))

- Crash on sortby None (default value)
  ([`d62164e`](https://github.com/enix/pvecontrol/commit/d62164efd964047e1813665e1a45bb67750c5c37))

- Crash when filtering returns 0 results
  ([`55bd00b`](https://github.com/enix/pvecontrol/commit/55bd00b8e7fbe075b35b5bb96935963669b6ddf8))

- Harmonize logs when using --wait and --follow
  ([`aac7714`](https://github.com/enix/pvecontrol/commit/aac77144f9191147ee08398cb5efcb5058bac3e8))

- Missing method self._initstatus() in task.refresh()
  ([`547bdd1`](https://github.com/enix/pvecontrol/commit/547bdd1585f0fcb6006e14a5f835429badef017c))

- Patch clusterconfig never set to default config
  ([`910a7ac`](https://github.com/enix/pvecontrol/commit/910a7ac44160cf5ef2b039a3eed96d9626f1d13a))

- Strenum isn't available for python 3.10
  ([`d32fffc`](https://github.com/enix/pvecontrol/commit/d32fffc06741c8ee2c7ff5d7a51ffe3e059992ae))

- Transpose existing sanity checks to new class
  ([`ea4ac51`](https://github.com/enix/pvecontrol/commit/ea4ac51bbb1b8841462b7a202ea29dfe5e90ad6a))

- **clusterstatus**: Update cli output
  ([`d6fac76`](https://github.com/enix/pvecontrol/commit/d6fac7698679eace9bd9cf87d86aab5e13cd7c4c))

- **config**: Correct PVECluster args node to config
  ([`c576f2e`](https://github.com/enix/pvecontrol/commit/c576f2ef11ff34c7253babba53eba9fa949c61a0))

- **config**: Correct PVECluster args node to config
  ([`92b030e`](https://github.com/enix/pvecontrol/commit/92b030e713f6559017b7858107c2e61e05bff0c1))

- **config**: Rollback node_factors to node
  ([`f5f5ec4`](https://github.com/enix/pvecontrol/commit/f5f5ec41d6d8444c9cb930f38e50b7c8701871fe))

- **evacuate**: Change log output
  ([`0433c60`](https://github.com/enix/pvecontrol/commit/0433c60b8188b206574094601869aa1a5a4cdb9e))

- **evacuate**: Make sure targets are unique
  ([`9266a25`](https://github.com/enix/pvecontrol/commit/9266a25f5b4a9e7c74e987690758e524670bc07a))

- **sanitycheck**: In VM config, cpu are not always return by API
  ([`7e40e21`](https://github.com/enix/pvecontrol/commit/7e40e219bde6f43a716815a2021084c9ccfa2074))

- **sanitycheck**: Patch error on if statements in ha_vms check
  ([`13f7fd5`](https://github.com/enix/pvecontrol/commit/13f7fd5d2e231bdb2a0ce5e5b10f206104821679))

- **sanitycheck**: Patch no checks append to sanity checks list
  ([`21341f8`](https://github.com/enix/pvecontrol/commit/21341f87758c4979ca26090c68e6f65bc8e75ac6))

- **sanitycheck**: Verify check exists before trying to run it
  ([`b83be42`](https://github.com/enix/pvecontrol/commit/b83be4269ede73d6b46bf56b8e4bdebadc1e8dc5))

- **sanitychecks**: Add exitcode and correct message criticity code
  ([`21f0864`](https://github.com/enix/pvecontrol/commit/21f0864a36fd8aef2fe7f421a56123f2190abc96))

- **sanitychecks**: Add terminal supports verification (utf-8, bold, colors)
  ([`1983eca`](https://github.com/enix/pvecontrol/commit/1983ecaf4592f7e5076aab6a516aa7c4c50fa8e5))

- **sanitychecks**: Correct check code for ha_group
  ([`16aca67`](https://github.com/enix/pvecontrol/commit/16aca67b94ac1094d5935c373617d6b0272ba505))

- **sanitychecks**: Patch display issues depending on terminal using curses
  ([`f69e07c`](https://github.com/enix/pvecontrol/commit/f69e07c9a83458b1270202134354c56bda4a861b))

- **sanitychecks**: Patch display issues depending on terminal using curses
  ([`6a9e93a`](https://github.com/enix/pvecontrol/commit/6a9e93ae6f4f38165844f44618c282eab1eb52ff))

- **sanitychecks**: Patch some issues
  ([`049d6e6`](https://github.com/enix/pvecontrol/commit/049d6e6caf74ab6ffacf66dffb9da4e9b1f8c382))

- **sanitychecks**: Refacto Checks run with classes
  ([`660a837`](https://github.com/enix/pvecontrol/commit/660a837dd0ad109e3f3abb2a2286943ee3ddf5ea))

- **storage**: Patch error on PVEStorage.__str__
  ([`9e71daa`](https://github.com/enix/pvecontrol/commit/9e71daaefd22344d71e93b7b86aaeac0266e820e))

- **storagelist**: Add sort-by arg
  ([`76337ab`](https://github.com/enix/pvecontrol/commit/76337ab53bc5a6c897be45fa234228e2b7ed1089))

- **storagelist**: Correct shared col
  ([`ee9d082`](https://github.com/enix/pvecontrol/commit/ee9d0829a69fccb4010a903996748b6eeccd8e5a))

- **storagelist**: Prototype of print_tableoutput has changed
  ([`f7e27cc`](https://github.com/enix/pvecontrol/commit/f7e27cc841f3bb5b310bc393b975eac3b697c033))

- **storagelist**: Update PVEStorage kwargs loading
  ([`43990a5`](https://github.com/enix/pvecontrol/commit/43990a5f20e221ad159be301f6ee5ddfe3b28a25))

- **tasks**: Nicely handle vanished tasks
  ([`1fbf112`](https://github.com/enix/pvecontrol/commit/1fbf112a6ed6604891bd5ebf86cc18ed79a2529a))

Some tasks can deseappear from the API with time. So we must handle this case.

### Chores

- Add CI job for black and config in pyproject
  ([`6b76a99`](https://github.com/enix/pvecontrol/commit/6b76a99164cb2f045ec4daaaa53c0d1adc688352))

- Fix ci cancelled jobs
  ([`e3c4af0`](https://github.com/enix/pvecontrol/commit/e3c4af0f0af058931e92f74a7b4ef7c5900c44d0))

- Optimize cli by reducing HTTP calls
  ([`f78a040`](https://github.com/enix/pvecontrol/commit/f78a040bdcdc3b54180021be0668df9bcaa12753))

- Remove Github deployment in CI stage tests
  ([`c35723c`](https://github.com/enix/pvecontrol/commit/c35723c6cd2b822d78bf4fd5c12a8f32fe908e64))

- Remove Github deployment in CI stage tests
  ([`8bdbceb`](https://github.com/enix/pvecontrol/commit/8bdbceb5b4e23e72e6588051fa5576d90ddc5d3b))

- Run black
  ([`12f1045`](https://github.com/enix/pvecontrol/commit/12f1045ed4849f59092003df03e91c714610d2c6))

- Run black
  ([`f4e5013`](https://github.com/enix/pvecontrol/commit/f4e5013c900eac05707655696b5ad6eabfc9d30e))

- **auth**: Patch tests and lint
  ([`3aa20b2`](https://github.com/enix/pvecontrol/commit/3aa20b2f8874d5ddcb0d4f5e0149c0002ffb8785))

- **black**: Correct style for sanitycheck
  ([`62e792e`](https://github.com/enix/pvecontrol/commit/62e792e97bf5ea35eddd895432c0779c1acacc87))

- **black**: Patch black warnings
  ([`800c157`](https://github.com/enix/pvecontrol/commit/800c1577ab71070c70b7bfce29a1abdef08a70bc))

- **ci**: Fix CI execution for PRs
  ([`2bf9fe8`](https://github.com/enix/pvecontrol/commit/2bf9fe88868155ce6443d75cdeb98238e0c1d548))

- **ci**: Update file requirements-dev.txt
  ([`3536c51`](https://github.com/enix/pvecontrol/commit/3536c5194f1859ce0eca889a99bbdf64a53d1453))

- **pylint**: Add CI job for pylint
  ([`58d29cd`](https://github.com/enix/pvecontrol/commit/58d29cd07312c5fc7719252b54c9919966188df9))

- **pylint**: Init pylint refacto
  ([`2712d88`](https://github.com/enix/pvecontrol/commit/2712d882eec1ecaabe23a7e9438f6fa14720e384))

- **pylint**: Patch last needed
  ([`17503b9`](https://github.com/enix/pvecontrol/commit/17503b966ed926cc76a1f6a669a9588da3b1a000))

- **pylint**: Patch loop on pvecontrol module
  ([`6eed68f`](https://github.com/enix/pvecontrol/commit/6eed68f0884342372227e74e6a92ac540c626a45))

- **pylint**: Patch pvecontrol/actions/cluster.py
  ([`62eb341`](https://github.com/enix/pvecontrol/commit/62eb341e5dcc42f6464e1f0ad240f7b37179f1d1))

- **pylint**: Patch pvecontrol/actions/storage.py
  ([`6669615`](https://github.com/enix/pvecontrol/commit/66696154d56bf0352f851ad209631a12c66ef18b))

- **pylint**: Patch pvecontrol/actions/task.py
  ([`3106b23`](https://github.com/enix/pvecontrol/commit/3106b23fb7895f5e9cd11410f828993c6b403327))

- **pylint**: Patch pvecontrol/actions/vm.py
  ([`d453dfb`](https://github.com/enix/pvecontrol/commit/d453dfbd83efa89d2bdc5fe7202738b67da5ed32))

- **pylint**: Patch pvecontrol/node.py
  ([`2a81710`](https://github.com/enix/pvecontrol/commit/2a817101c1792071a110357f39b1856bd2404d29))

- **pylint**: Patch src/pvecontrol/cluster.py
  ([`d1e1f78`](https://github.com/enix/pvecontrol/commit/d1e1f7850d405dffeb3540026f8c4c2ff5041a5d))

- **pylint**: Patch src/pvecontrol/storage.py
  ([`e3582ad`](https://github.com/enix/pvecontrol/commit/e3582ad360ad91c1fbd7f1596a8d4e5fdbc94b1d))

- **pylint**: Patch src/pvecontrol/utils.py
  ([`509f911`](https://github.com/enix/pvecontrol/commit/509f91128d908f18d0e6595e5b9e100a6b0f32f8))

- **pylint**: Patch typo
  ([`6308701`](https://github.com/enix/pvecontrol/commit/630870192280a84e699101b86ec0559b2d83aa1e))

- **pylint**: Rebase to branch black
  ([`149ee27`](https://github.com/enix/pvecontrol/commit/149ee27e702bb7c5625e0a7901188c2acb5a8064))

- **pylint**: Remove unnecessary pylint comment
  ([`77e8329`](https://github.com/enix/pvecontrol/commit/77e832919c2bbedcba2452b2c6dca5b52dc1814d))

- **README**: Add documentation about shell auto completion
  ([`239ef7a`](https://github.com/enix/pvecontrol/commit/239ef7a9618bac806d4a78c28799f25802a02c7d))

- **README**: Complete doc for release
  ([`56d2fea`](https://github.com/enix/pvecontrol/commit/56d2fea73691cf69265e57b853fad37f7e61d9a6))

* docs: update README

* chore(README): Add token auth to documentation.

* docs: merge my token auth docs

---------

Co-authored-by: Laurent Corbes <laurent.corbes@enix.fr>

- **README**: Fix missing newline
  ([`53e6924`](https://github.com/enix/pvecontrol/commit/53e6924ab1a2d626c549bee3220fe287f16af9f9))

- **README**: Fix title
  ([`5897f2a`](https://github.com/enix/pvecontrol/commit/5897f2a8b7af270b82d2c5a80952ee79c21df70d))

- **README**: With pylint modification dev command was updated
  ([`d4071f6`](https://github.com/enix/pvecontrol/commit/d4071f6657bc8510c8eac79a062c19b2cba41783))

### Features

- --columns flag
  ([`ef518d9`](https://github.com/enix/pvecontrol/commit/ef518d93e00e5cb8e94aa0b2ecb177441b1a043a))

- Add --filter flag to node, task and vm
  ([`65691ae`](https://github.com/enix/pvecontrol/commit/65691ae594194ca499f90ed751ae40a3ca9a95ca))

- Add --output option to list commands (supports text, json, csv and yaml)
  ([`889dc9a`](https://github.com/enix/pvecontrol/commit/889dc9aad6e1742bc0caf7364663399e7b29fc0f))

- Add --sort-by flag
  ([`e87a8cc`](https://github.com/enix/pvecontrol/commit/e87a8cc4073b9022b4e2be7c9f370fd834fbc456))

- Add completion generation
  ([`c431b37`](https://github.com/enix/pvecontrol/commit/c431b37e442b783fc5261c1b6d67e459eddd5819))

- Add sanitycheck VM has HA disks
  ([`df14e9e`](https://github.com/enix/pvecontrol/commit/df14e9e86b8a6ade11302c6911985604cd07dc48))

- Add sanitycheck VM has HA disks
  ([`81ca806`](https://github.com/enix/pvecontrol/commit/81ca8066625b943eb8f85ab326c0c8abdc79f6ac))

- Add shell-like globbing on nodeevacuate --target flag
  ([`8ae1582`](https://github.com/enix/pvecontrol/commit/8ae15823a7cb29bca3c74d77498b93e37fd1fd7a))

based on fnmatch.fnmatchcase from python stdlib

- Add support for authentication tokens
  ([`1e44bb8`](https://github.com/enix/pvecontrol/commit/1e44bb8cfb3024274d1214e13c4d7495819cf872))

- Columns name validation (--sort-by & --filter flags)
  ([`e59e1ac`](https://github.com/enix/pvecontrol/commit/e59e1acd4936c8c7a7e56e3ab9d27dbbc1fcca3e))

- Implement cpufactor and memoryminimum by cluster
  ([`e6e4f8f`](https://github.com/enix/pvecontrol/commit/e6e4f8f5c182aca2d316688fd0fc32ba7b0e6eaa))

- **auth**: Add some checks on token auth
  ([`bf4ffa5`](https://github.com/enix/pvecontrol/commit/bf4ffa586a0701a2ddd800291d8646f7b933ff95))

- **auth**: Allow command on user, password config attributes
  ([`8679dbc`](https://github.com/enix/pvecontrol/commit/8679dbc2eca9df285908db0e6989b0d116409805))

- **auth**: Allow command on user, password config attributes
  ([`90d41e9`](https://github.com/enix/pvecontrol/commit/90d41e9906fbe971a642b6d530a87c4adb82b2d3))

- **auth**: Allow command on user, password config attributes
  ([`2d46e63`](https://github.com/enix/pvecontrol/commit/2d46e63eb469f9e2d8a25176283a498031e7c4ab))

- **auth**: Update README.md
  ([`50ec2e0`](https://github.com/enix/pvecontrol/commit/50ec2e02349267760011889c7800a320622b1081))

- **node**: Nodeevacuate add --wait flag
  ([`1235191`](https://github.com/enix/pvecontrol/commit/1235191cef0b8a2d36db073c753aa89bc558fac5))

- **sanitycheck**: Check HA VM has cpu type != host
  ([`f6d4c39`](https://github.com/enix/pvecontrol/commit/f6d4c39777c247de9d92df5cc0e39cbf0caa208d))

- **sanitycheck**: Rewrite logic to run tests
  ([`b2d8a50`](https://github.com/enix/pvecontrol/commit/b2d8a505ece8f916642cc77c0a9daa70d768135c))

- **sanitychecks**: Add colors support on ASCII icons
  ([`de28a97`](https://github.com/enix/pvecontrol/commit/de28a97f9740ae0ed992287cedb5b799a852b6db))

- **storagelist**: Add missing --filter flag
  ([`bbf348e`](https://github.com/enix/pvecontrol/commit/bbf348e8804679ded0b9b9d98a11a0937ab462ec))

- **storagelist**: Add storages list group shared by storage name
  ([`1f0be0e`](https://github.com/enix/pvecontrol/commit/1f0be0e6c55d6247ae424716440c0f89a70a5642))

- **tasks**: Taskget add --wait flag
  ([`87dd240`](https://github.com/enix/pvecontrol/commit/87dd2407252134aca5d9bf35bf4e60da9c282afd))

- **vm**: Vmmigrate add --wait flag
  ([`13c1bed`](https://github.com/enix/pvecontrol/commit/13c1bedec9847c265f290b7c0e6ed39726272ea5))

### Refactoring

- Default values of PVE objects (node, vm & task)
  ([`a49a56c`](https://github.com/enix/pvecontrol/commit/a49a56c7c7d138f9cdbf4537dae6aab2572ab70a))

- Move tests in src directory
  ([`ff64315`](https://github.com/enix/pvecontrol/commit/ff643158836c2f97e2fdf0e8064ade21030101da))

- Simplify print_task
  ([`5d42984`](https://github.com/enix/pvecontrol/commit/5d429848ec98291126b66fd3bf6e31f782ee014c))


## v0.4.0 (2024-11-04)

### Bug Fixes

- Patch test
  ([`902fd2a`](https://github.com/enix/pvecontrol/commit/902fd2ac90ffd5b2282a45094d1a6dcc32df9020))

- Pep8 compliance update private method
  ([`8d260b3`](https://github.com/enix/pvecontrol/commit/8d260b3c5530218c8e2a03ff514a35ba98709962))

### Features

- Split actions into mutliple files, add a config.py to resolve issue due to global validconfig
  ([`32f4534`](https://github.com/enix/pvecontrol/commit/32f4534aa8702a82d800d1f1e3e099cae11e762b))


## v0.3.1 (2024-10-02)

### Bug Fixes

- **package**: Fix module package and install
  ([`858d20f`](https://github.com/enix/pvecontrol/commit/858d20f6bde59b0140a1ca7dd68afd5818bfe05e))

### Chores

- **ci**: Update python version
  ([`c79b5a3`](https://github.com/enix/pvecontrol/commit/c79b5a341acdf840824b3e74f836be80b265bc39))

Also update action versions Run ci on dev branch


## v0.3.0 (2024-10-01)

### Bug Fixes

- **node**: Add cast on memory
  ([`2298276`](https://github.com/enix/pvecontrol/commit/229827651a99dd68838b91b5b0a05900ede37220))

- **node**: Linter output
  ([`5e0bea1`](https://github.com/enix/pvecontrol/commit/5e0bea113ba728b457ed0d1bd7626be22f907e66))

- **PVENode**: Fix issue with offline node
  ([`a128eb3`](https://github.com/enix/pvecontrol/commit/a128eb3be53071503cdd6769279021ec0bb64d12))

- **task**: Fix issue with status refresh
  ([`43c72c0`](https://github.com/enix/pvecontrol/commit/43c72c01fac3ea5b03d931d7b44d13c226012f15))

- **task**: Revert fix for not available node
  ([`3cbd35a`](https://github.com/enix/pvecontrol/commit/3cbd35a98504b61b79aaba817117c32e2093facd))

### Chores

- **pvecontrol**: Add some debug
  ([`21d332a`](https://github.com/enix/pvecontrol/commit/21d332af8f416c060654169b604ed1ed0b23c980))

- **README**: Update config
  ([`4f62fc7`](https://github.com/enix/pvecontrol/commit/4f62fc7af56da5aaa7bd3ed388e4b071c7bab9a7))

### Features

- **cluster**: Add refresh
  ([`6b50de5`](https://github.com/enix/pvecontrol/commit/6b50de5bd36becbface74638a6fb6f4345e074f4))

Allow to refresh all clusters objects

- **global**: Complete rewrite into classes
  ([`119b01c`](https://github.com/enix/pvecontrol/commit/119b01cc42355d93db1f8c8afd77427ce1b7a5ab))

Create classes to manage PVECluster, PVENode and PVEVM objects. This will allow lot more simple
  operations now.

- **pvecontrol**: Add nodeevacuate feature
  ([`206dc83`](https://github.com/enix/pvecontrol/commit/206dc8322cf8fc7eb0bae3c3385fef4bd7f8a7ea))

This fonction allow to automatically migrate out all the VMs from a node to another ones.

- **sanitycheck**: Add feature to check for cluster good rules
  ([`f649380`](https://github.com/enix/pvecontrol/commit/f64938077d41a745c04b306d27754c43a1500c67))

- **task**: Add internal decode_log fonction
  ([`dad15b2`](https://github.com/enix/pvecontrol/commit/dad15b22e1fdeade956bfadba66283d0aa9ce835))

- **tasks**: Rewrite task using class
  ([`df528be`](https://github.com/enix/pvecontrol/commit/df528be678de9b6cfd2cf822ffcaedaf7db2c280))

- **vm**: Add vm.migrate
  ([`9b01237`](https://github.com/enix/pvecontrol/commit/9b012372c038e451b2898fdff9f0a169940300d4))

This new fonction take over management of VM migration


## v0.2.0 (2023-10-06)

### Bug Fixes

- **config**: Use a more comprehensive default
  ([`5b9d4fc`](https://github.com/enix/pvecontrol/commit/5b9d4fc98ab6461cab30a89d242a440425e81b3c))

- **nodelist**: Add some defaults for optional
  ([`f1ece32`](https://github.com/enix/pvecontrol/commit/f1ece32b936d1f8d187abd4426fa08de0a0ce6e8))

- **pvecontrol**: Convert vmid to int
  ([`bb493fa`](https://github.com/enix/pvecontrol/commit/bb493fa4d1dac1f9e8d8e888957e6684e3f706be))

- **pvecontrol**: Update parser help output
  ([`4a484f3`](https://github.com/enix/pvecontrol/commit/4a484f310c0c23dfababd7e700bf4d3678653fee))

- **requirements**: Bump proxmoxer version
  ([`09fd1fb`](https://github.com/enix/pvecontrol/commit/09fd1fb06e0c4b1f37e315855f2ae9260bf8b6ce))

### Chores

- **debug**: Add some debug lines
  ([`151c31d`](https://github.com/enix/pvecontrol/commit/151c31df02d6da841debc85a7a3cb1df004c18b0))

- **README**: Add badges, fix typos
  ([`e51df76`](https://github.com/enix/pvecontrol/commit/e51df76aa0625c0c9e40ed95215c16ce06964175))

- **README**: More complete documentation
  ([`384749c`](https://github.com/enix/pvecontrol/commit/384749c052b2fa37cd152b175aca517d116b8fc9))

- **setup**: Change description
  ([`542f9d7`](https://github.com/enix/pvecontrol/commit/542f9d7594fa47384753335e57382505b6bb2b16))

- **setup**: Change README content type
  ([`08aabcb`](https://github.com/enix/pvecontrol/commit/08aabcbde7cc6630e86029da965ed1fb25d84a91))

### Features

- **vmmigrate**: Add dry-run
  ([`9a5941e`](https://github.com/enix/pvecontrol/commit/9a5941e8639bc0c5010bbaa1911fe6ac368a36d1))

- **vmmigrate**: First version with migration
  ([`c908672`](https://github.com/enix/pvecontrol/commit/c908672e60ab60029a1b2c71ec9edce5edc41111))


## v0.1.1 (2023-09-13)

### Bug Fixes

- **pvecontrol**: Add missing empty line
  ([`b825a95`](https://github.com/enix/pvecontrol/commit/b825a9516a48c70a950cb8faf4bd9113f981ccbc))

### Chores

- **README**: Update python version
  ([`14b4ad1`](https://github.com/enix/pvecontrol/commit/14b4ad17cc2245db9540915c4fd1cf30acba1a80))

- **release**: Use unified release workflow
  ([`6c481a7`](https://github.com/enix/pvecontrol/commit/6c481a7f81c755fd685d6111071469955b0660a9))


## v0.1.0 (2023-09-13)

### Features

- **semantic-release**: Add semantic-release configuration
  ([`d1c86b5`](https://github.com/enix/pvecontrol/commit/d1c86b513fc3ab7a6b402b0156cd1b16b8481d4e))

This include semantic-release gh action to build a new release when push to main branch


## v0.0.1 (2023-09-13)

### Bug Fixes

- **allocated_cpu**: Sockets is optional
  ([`a858e9b`](https://github.com/enix/pvecontrol/commit/a858e9b5d00f6dd6c848d27e1a135bb42f23eff4))

- **main**: Proper definition of main function
  ([`8253449`](https://github.com/enix/pvecontrol/commit/8253449163635a2f32f2e1e74dd76208b2beb853))

- **nodelist**: Skip offline nodes
  ([`9c67414`](https://github.com/enix/pvecontrol/commit/9c6741488365555f8a578eb029e4fead3dae47e5))

- **taskget**: Fix output of running tasks
  ([`b720c1b`](https://github.com/enix/pvecontrol/commit/b720c1b30cf71dae66ce0828f84d45d497d4d2cb))

### Chores

- **package**: Add gh action package
  ([`477e243`](https://github.com/enix/pvecontrol/commit/477e243f41abc8cfe9621f601210dcf65d49df97))

- **requirements**: Update requirements.txt
  ([`8d58ae1`](https://github.com/enix/pvecontrol/commit/8d58ae1fec5dd0810250bde2beedb365fcf09352))

- **test**: Add simple test
  ([`2a6e14e`](https://github.com/enix/pvecontrol/commit/2a6e14e663023df32e333cdf917228179eba1b40))

### Features

- **get_nodes**: New fonction
  ([`41fc8ae`](https://github.com/enix/pvecontrol/commit/41fc8aefdd7dfe314e4f836a9dbb3013105489c6))

- **gettasks**: New function
  ([`f479bf4`](https://github.com/enix/pvecontrol/commit/f479bf475506219623ff178eee3e5d8ccce5c1a2))

- **packaging**: Package the app
  ([`63e3bec`](https://github.com/enix/pvecontrol/commit/63e3bec60619d4db58077265fac4746d90213c24))

- **taskget**: Get task details
  ([`f2a4b14`](https://github.com/enix/pvecontrol/commit/f2a4b143c145a5a60ccebd8404ab11cc32652158))

- **taskget**: Get task informations and logs
  ([`85f1e1c`](https://github.com/enix/pvecontrol/commit/85f1e1c38fcdf5dddf47810453c09bcb69adaf2f))

- **tasklist**: Rename function
  ([`3b449f5`](https://github.com/enix/pvecontrol/commit/3b449f56ce8ca939e17e15f1ee3fcd04c61c2b52))
