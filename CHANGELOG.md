# CHANGELOG


## v0.4.0 (2024-11-04)

### Bug Fixes

* fix: PEP8 compliance update private method ([`8d260b3`](https://github.com/enix/pvecontrol/commit/8d260b3c5530218c8e2a03ff514a35ba98709962))

* fix: Patch test ([`902fd2a`](https://github.com/enix/pvecontrol/commit/902fd2ac90ffd5b2282a45094d1a6dcc32df9020))

### Features

* feat: Split actions into mutliple files, add a config.py to resolve issue due to global validconfig ([`32f4534`](https://github.com/enix/pvecontrol/commit/32f4534aa8702a82d800d1f1e3e099cae11e762b))


## v0.3.1 (2024-10-02)

### Bug Fixes

* fix(package): Fix module package and install ([`858d20f`](https://github.com/enix/pvecontrol/commit/858d20f6bde59b0140a1ca7dd68afd5818bfe05e))

### Chores

* chore(ci): update python version

Also update action versions
Run ci on dev branch ([`c79b5a3`](https://github.com/enix/pvecontrol/commit/c79b5a341acdf840824b3e74f836be80b265bc39))


## v0.3.0 (2024-10-01)

### Bug Fixes

* fix(task): Fix issue with status refresh ([`43c72c0`](https://github.com/enix/pvecontrol/commit/43c72c01fac3ea5b03d931d7b44d13c226012f15))

* fix(node): linter output ([`5e0bea1`](https://github.com/enix/pvecontrol/commit/5e0bea113ba728b457ed0d1bd7626be22f907e66))

* fix(task): Revert fix for not available node ([`3cbd35a`](https://github.com/enix/pvecontrol/commit/3cbd35a98504b61b79aaba817117c32e2093facd))

* fix(node): add cast on memory ([`2298276`](https://github.com/enix/pvecontrol/commit/229827651a99dd68838b91b5b0a05900ede37220))

* fix(PVENode): Fix issue with offline node ([`a128eb3`](https://github.com/enix/pvecontrol/commit/a128eb3be53071503cdd6769279021ec0bb64d12))

### Chores

* chore(README): Update config ([`4f62fc7`](https://github.com/enix/pvecontrol/commit/4f62fc7af56da5aaa7bd3ed388e4b071c7bab9a7))

* chore(pvecontrol): Add some debug ([`21d332a`](https://github.com/enix/pvecontrol/commit/21d332af8f416c060654169b604ed1ed0b23c980))

### Features

* feat(pvecontrol): Add nodeevacuate feature

This fonction allow to automatically migrate out all the VMs from a node to another ones. ([`206dc83`](https://github.com/enix/pvecontrol/commit/206dc8322cf8fc7eb0bae3c3385fef4bd7f8a7ea))

* feat(task): Add internal decode_log fonction ([`dad15b2`](https://github.com/enix/pvecontrol/commit/dad15b22e1fdeade956bfadba66283d0aa9ce835))

* feat(cluster): Add refresh

Allow to refresh all clusters objects ([`6b50de5`](https://github.com/enix/pvecontrol/commit/6b50de5bd36becbface74638a6fb6f4345e074f4))

* feat(vm): add vm.migrate

This new fonction take over management of VM migration ([`9b01237`](https://github.com/enix/pvecontrol/commit/9b012372c038e451b2898fdff9f0a169940300d4))

* feat(sanitycheck): Add feature to check for cluster good rules ([`f649380`](https://github.com/enix/pvecontrol/commit/f64938077d41a745c04b306d27754c43a1500c67))

* feat(tasks): Rewrite task using class ([`df528be`](https://github.com/enix/pvecontrol/commit/df528be678de9b6cfd2cf822ffcaedaf7db2c280))

* feat(global): Complete rewrite into classes

Create classes to manage PVECluster, PVENode and PVEVM objects. This will allow
lot more simple operations now. ([`119b01c`](https://github.com/enix/pvecontrol/commit/119b01cc42355d93db1f8c8afd77427ce1b7a5ab))

### Unknown

* Merge pull request #3 from enix/dev

Split code using lib and objects ([`b411d19`](https://github.com/enix/pvecontrol/commit/b411d19a2136973ce26613e202a5a5d53da744f8))


## v0.2.0 (2023-10-06)

### Bug Fixes

* fix(pvecontrol): Update parser help output ([`4a484f3`](https://github.com/enix/pvecontrol/commit/4a484f310c0c23dfababd7e700bf4d3678653fee))

* fix(requirements): Bump proxmoxer version ([`09fd1fb`](https://github.com/enix/pvecontrol/commit/09fd1fb06e0c4b1f37e315855f2ae9260bf8b6ce))

* fix(config): Use a more comprehensive default ([`5b9d4fc`](https://github.com/enix/pvecontrol/commit/5b9d4fc98ab6461cab30a89d242a440425e81b3c))

* fix(pvecontrol): convert vmid to int ([`bb493fa`](https://github.com/enix/pvecontrol/commit/bb493fa4d1dac1f9e8d8e888957e6684e3f706be))

* fix(nodelist): add some defaults for optional ([`f1ece32`](https://github.com/enix/pvecontrol/commit/f1ece32b936d1f8d187abd4426fa08de0a0ce6e8))

### Chores

* chore(README): Add badges, fix typos ([`e51df76`](https://github.com/enix/pvecontrol/commit/e51df76aa0625c0c9e40ed95215c16ce06964175))

* chore(README): More complete documentation ([`384749c`](https://github.com/enix/pvecontrol/commit/384749c052b2fa37cd152b175aca517d116b8fc9))

* chore(debug): Add some debug lines ([`151c31d`](https://github.com/enix/pvecontrol/commit/151c31df02d6da841debc85a7a3cb1df004c18b0))

* chore(setup): Change description ([`542f9d7`](https://github.com/enix/pvecontrol/commit/542f9d7594fa47384753335e57382505b6bb2b16))

* chore(setup): Change README content type ([`08aabcb`](https://github.com/enix/pvecontrol/commit/08aabcbde7cc6630e86029da965ed1fb25d84a91))

### Features

* feat(vmmigrate): Add dry-run ([`9a5941e`](https://github.com/enix/pvecontrol/commit/9a5941e8639bc0c5010bbaa1911fe6ac368a36d1))

* feat(vmmigrate): First version with migration ([`c908672`](https://github.com/enix/pvecontrol/commit/c908672e60ab60029a1b2c71ec9edce5edc41111))

### Unknown

* Merge pull request #2 from enix/dev

New release ([`98ea199`](https://github.com/enix/pvecontrol/commit/98ea199539a8766fe2bda4c7979f101e571d104f))

* Merge pull request #1 from enix/rdegez-patch-1

Update README.md ([`e65bd77`](https://github.com/enix/pvecontrol/commit/e65bd7704d57c04a1297aef3a8134d8221af7cc8))

* Update README.md

Fix typos ([`4fb2d47`](https://github.com/enix/pvecontrol/commit/4fb2d47dabdce0a75183b424eb8a53fbf0c9accc))


## v0.1.1 (2023-09-13)

### Bug Fixes

* fix(pvecontrol): Add missing empty line ([`b825a95`](https://github.com/enix/pvecontrol/commit/b825a9516a48c70a950cb8faf4bd9113f981ccbc))

### Chores

* chore(README): update python version ([`14b4ad1`](https://github.com/enix/pvecontrol/commit/14b4ad17cc2245db9540915c4fd1cf30acba1a80))

* chore(release): Use unified release workflow ([`6c481a7`](https://github.com/enix/pvecontrol/commit/6c481a7f81c755fd685d6111071469955b0660a9))


## v0.1.0 (2023-09-13)

### Features

* feat(semantic-release): Add semantic-release configuration

This include semantic-release gh action to build a new release when push
to main branch ([`d1c86b5`](https://github.com/enix/pvecontrol/commit/d1c86b513fc3ab7a6b402b0156cd1b16b8481d4e))


## v0.0.1 (2023-09-13)

### Bug Fixes

* fix(main): proper definition of main function ([`8253449`](https://github.com/enix/pvecontrol/commit/8253449163635a2f32f2e1e74dd76208b2beb853))

* fix(taskget): fix output of running tasks ([`b720c1b`](https://github.com/enix/pvecontrol/commit/b720c1b30cf71dae66ce0828f84d45d497d4d2cb))

* fix(nodelist): skip offline nodes ([`9c67414`](https://github.com/enix/pvecontrol/commit/9c6741488365555f8a578eb029e4fead3dae47e5))

* fix(allocated_cpu): sockets is optional ([`a858e9b`](https://github.com/enix/pvecontrol/commit/a858e9b5d00f6dd6c848d27e1a135bb42f23eff4))

### Chores

* chore(test): Add simple test ([`2a6e14e`](https://github.com/enix/pvecontrol/commit/2a6e14e663023df32e333cdf917228179eba1b40))

* chore(requirements): Update requirements.txt ([`8d58ae1`](https://github.com/enix/pvecontrol/commit/8d58ae1fec5dd0810250bde2beedb365fcf09352))

* chore(package): add gh action package ([`477e243`](https://github.com/enix/pvecontrol/commit/477e243f41abc8cfe9621f601210dcf65d49df97))

### Features

* feat(packaging): Package the app ([`63e3bec`](https://github.com/enix/pvecontrol/commit/63e3bec60619d4db58077265fac4746d90213c24))

* feat(taskget): get task informations and logs ([`85f1e1c`](https://github.com/enix/pvecontrol/commit/85f1e1c38fcdf5dddf47810453c09bcb69adaf2f))

* feat(taskget): get task details ([`f2a4b14`](https://github.com/enix/pvecontrol/commit/f2a4b143c145a5a60ccebd8404ab11cc32652158))

* feat(tasklist): rename function ([`3b449f5`](https://github.com/enix/pvecontrol/commit/3b449f56ce8ca939e17e15f1ee3fcd04c61c2b52))

* feat(gettasks): new function ([`f479bf4`](https://github.com/enix/pvecontrol/commit/f479bf475506219623ff178eee3e5d8ccce5c1a2))

* feat(get_nodes): new fonction ([`41fc8ae`](https://github.com/enix/pvecontrol/commit/41fc8aefdd7dfe314e4f836a9dbb3013105489c6))

### Unknown

* Create python-publish.yml ([`9fea026`](https://github.com/enix/pvecontrol/commit/9fea026976cadd99a3807575af8f3405d455fa15))

* add some clusterstatus fonction ([`ec6e906`](https://github.com/enix/pvecontrol/commit/ec6e906ee15018a8f6c3040cb7f8af5583d18b5e))

* Add some logging ([`c85e29e`](https://github.com/enix/pvecontrol/commit/c85e29e4e9ce30df199f5d5b503fde4b787e1060))

* Add readme ([`283442e`](https://github.com/enix/pvecontrol/commit/283442e12707b26f906bd2cfe528226ca8098dab))

* Add .gitignore ([`b57f981`](https://github.com/enix/pvecontrol/commit/b57f9818f626bc8772f88b5f972b797271d08bf2))

* Add python requirement ([`18e5856`](https://github.com/enix/pvecontrol/commit/18e58563a42e239ea09c01c8f5bd9ce25ecd8843))

* First working version ([`bc70239`](https://github.com/enix/pvecontrol/commit/bc70239c56a902cdebe15e4307eab2194b5e8d32))

* more experiment ([`8adc444`](https://github.com/enix/pvecontrol/commit/8adc44409f57cbf72f35b66315719c6f15ace8c6))

* First nodelist release.

This is an import of older script asis ([`363c088`](https://github.com/enix/pvecontrol/commit/363c0888028ad46f8af26f836e4f798e892895ff))

* First template ([`7c1d317`](https://github.com/enix/pvecontrol/commit/7c1d317ad9bea0f84bc01d6aac59424e8ed83fda))
