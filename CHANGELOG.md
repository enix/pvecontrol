# CHANGELOG


## v0.6.1 (2025-06-04)

### Bug Fixes

- Better sanity check output
  ([`aad6126`](https://github.com/enix/pvecontrol/commit/aad6126509f76b906b1dcb80205195c49d8c46ea))

- Patch terminal display
  ([`e86f30d`](https://github.com/enix/pvecontrol/commit/e86f30d4bc0c30125ef95e37e729f7a1d3bb2bf0))

- **migration**: Change default value of --online option
  ([`4b1508b`](https://github.com/enix/pvecontrol/commit/4b1508b6b911a93e404967e07de14b0efd459e62))

### Build System

- Use python-semantic-release v9 instead of master
  ([`da11a91`](https://github.com/enix/pvecontrol/commit/da11a91718f60b8e611de7618810eb9beea5a36c))

### Chores

- Update README.md
  ([`0eb4fc9`](https://github.com/enix/pvecontrol/commit/0eb4fc9d966d821ee19189dc6410a3006761c733))


## v0.6.0 (2025-05-12)

### Bug Fixes

- Bad formatting in "no such cluster" log
  ([`8d333d1`](https://github.com/enix/pvecontrol/commit/8d333d1fa200829bb73c436dcfdd26c25f7d3b3f))

- Enable ssl_verification from config, catch failures
  ([`c82c9e4`](https://github.com/enix/pvecontrol/commit/c82c9e4b140f56d5be6dc4d694faff8181d256e8))

- Exit 130 without printing stacktrace on sigint
  ([`bffe5d1`](https://github.com/enix/pvecontrol/commit/bffe5d1b9e432f6047627913a0c4d9d9ab28102a))

- Get version with help command, README typos
  ([`d4ac84f`](https://github.com/enix/pvecontrol/commit/d4ac84f35a5e111002393ebe700a6320911bc15f))

- Rebase click changes, more stuffs broken with json/yaml translator
  ([`fbab03a`](https://github.com/enix/pvecontrol/commit/fbab03aecd7a4af7735ea76ae70927b80da71406))

- Rm duped main (pip should gen the executable script)
  ([`a5fb557`](https://github.com/enix/pvecontrol/commit/a5fb557e453894815c992d743e53312cecf4d144))

- Set default memoryminimum to 8GB (8589934592 instead of 81928589934592)
  ([`c22ec97`](https://github.com/enix/pvecontrol/commit/c22ec977868d42e1590fc56f8c1b482e37743ff0))

The value was almost good, but prefixed with 8192, which is almost good also. But all together, it
  wasn't good at all.

- Set default when assigning resource_* prop (KeyError on faulty nodes)
  ([`53e2c2e`](https://github.com/enix/pvecontrol/commit/53e2c2ebd17dcda0fc4913342a5137f5d8f11c6a))

- Typo, incorrect status ref
  ([`afab5ae`](https://github.com/enix/pvecontrol/commit/afab5ae7a2608a1421d5fa74cfb09cbe3c6b8f7d))

- Use env in she-bangs
  ([`de6a25d`](https://github.com/enix/pvecontrol/commit/de6a25d20264ffed1390bcb988e60e73f363c00b))

- **config**: Set default timeout to 60
  ([`13a58ad`](https://github.com/enix/pvecontrol/commit/13a58ad490a89463ef85ec79e966a718f4c3f239))

- **sanitycheck**: Correct disk unused on check
  ([`ee32fc1`](https://github.com/enix/pvecontrol/commit/ee32fc1e6feb53fd05835c6999a0c2fa8f9790de))

- **sanitycheck**: Fix wording in backup messages
  ([`3e599e1`](https://github.com/enix/pvecontrol/commit/3e599e1071e5024bbc4cebae71e993a1e28ea4d4))

- **sanitycheck**: Patch VM startonboot option check
  ([`1ded8c4`](https://github.com/enix/pvecontrol/commit/1ded8c424ef24901399ad33d8b5255d52e3b6f20))

- **sanitycheck**: Reduce complexity on VMStartOnBoot check
  ([`591c60f`](https://github.com/enix/pvecontrol/commit/591c60f32da2bcdd970a220a324182dafda1ebc7))

- **sanitycheck**: Warn when vms don't have any backup
  ([`b86ea89`](https://github.com/enix/pvecontrol/commit/b86ea8955b4f26e219689c152ddbc0787fca742d))

- **sanitycheck**: Wording
  ([`fb10b29`](https://github.com/enix/pvecontrol/commit/fb10b292e484e3d070f8bf8372fb398e77aec4fd))

- **test**: Correct code repetition
  ([`f8f9625`](https://github.com/enix/pvecontrol/commit/f8f96253aa68f37413a94c89a2a491c01f0bc61f))

- **vm**: Add tags as vm columns
  ([`6a48132`](https://github.com/enix/pvecontrol/commit/6a48132123c8ffa677dceda56d07da0f25d43fbb))

- **vm**: Correctly parse tag list
  ([`c6f7e78`](https://github.com/enix/pvecontrol/commit/c6f7e7842677ca941409d732b343540b507ac35f))

- **vm**: Get_backup_jobs when selection mode is "all" or "exclude selected" and filter by node
  ([`b10ba25`](https://github.com/enix/pvecontrol/commit/b10ba25a410eb8c7b219528dfe8ef8f08a4c4abf))

- **vm**: Get_backup_jobs when selection mode is "pool based"
  ([`0cf55ef`](https://github.com/enix/pvecontrol/commit/0cf55efa65926cbb38ccb3db8173a96743a641b7))

- **vmstatus**: Add new VmStatus
  ([`fa20415`](https://github.com/enix/pvecontrol/commit/fa2041543dc1284652aaa3d17d8554601823ec37))

### Build System

- Trigger release manually from main branch only
  ([`5ff5bbd`](https://github.com/enix/pvecontrol/commit/5ff5bbda9e9bad6fc149b966434eb3559424153f))

- **ci**: Enable pip dependencies caching
  ([`7e9a391`](https://github.com/enix/pvecontrol/commit/7e9a3918cf51b71838296a6e8cf3587408b22da3))

- **ci**: Fetch with default depth (1 commit) instead of the whole history
  ([`f569685`](https://github.com/enix/pvecontrol/commit/f56968528cf263b0fff35e2baa981600a6370451))

- **ci**: Install pvecontrol package before running tests
  ([`949a85e`](https://github.com/enix/pvecontrol/commit/949a85ea258d0eac6821a9b3b131787ed9d453d2))

- **ci**: Remove flake8 linting and redundant pytest job
  ([`8c41a46`](https://github.com/enix/pvecontrol/commit/8c41a46e923559e846ffc0c2acb0ae9592ff81e8))

- **ci**: Trigger tests on pull requests but not on push
  ([`a04dc02`](https://github.com/enix/pvecontrol/commit/a04dc02d07c8e59c59c87ddc253272588ff86b73))

- **ci**: Upgrade actions versions
  ([`b72f95a`](https://github.com/enix/pvecontrol/commit/b72f95a9dfe5e5266a7df37c3306c1003102bd76))

### Chores

- Drop python-3.8 support, enable python-3.13
  ([`df51da3`](https://github.com/enix/pvecontrol/commit/df51da3e809152c0b1eee312e19a445b406332ff))

- Enable 'diff' option with black formatter
  ([`9d1edd5`](https://github.com/enix/pvecontrol/commit/9d1edd53c23ec8cb368b4fdcd81373dd7f3efdf8))

- Move root models to a dedicated folder
  ([`71fdc63`](https://github.com/enix/pvecontrol/commit/71fdc631124d74dc6beea022645ba14df322219d))

- **black**: Fix syntax
  ([`394b83e`](https://github.com/enix/pvecontrol/commit/394b83e21c28a2428ad45d2294aaeb3e3a104ee1))

- **cluster**: Add some logging around backups
  ([`ff863f8`](https://github.com/enix/pvecontrol/commit/ff863f8298aa7a99ee81cb34d3eccc7b39a386a4))

- **README**: Update fish completion documentation
  ([`c68bb6c`](https://github.com/enix/pvecontrol/commit/c68bb6cf6ed270871ea01fa88f5e869eafb5d90e))

### Documentation

- A command in README was using the legacy syntax
  ([`25cb79e`](https://github.com/enix/pvecontrol/commit/25cb79e47728810467feb6061f9cf4425383029b))

### Features

- Add a markdown outputFormat
  ([`fd9613f`](https://github.com/enix/pvecontrol/commit/fd9613f3743957babf744296ab061116ba316315))

- Add api timeout configuration
  ([`d2291ff`](https://github.com/enix/pvecontrol/commit/d2291ff8b3b3a238d92f239be1b57f2d9e1c24e8))

- Add list of available checks in sanitycheck --help
  ([`202eff5`](https://github.com/enix/pvecontrol/commit/202eff5bc19435f0c879982408197658f6cf20e3))

- Allow sorting and filtering on hidden columns
  ([`ce59a7a`](https://github.com/enix/pvecontrol/commit/ce59a7a764f9f84672162aa3388700f739f11022))

In render_output, we stopped using `filter_keys`, in order to be able to sort and filter on hidden
  columns as well. Instead, we use `reorder_keys` because filter_keys used to reorder keys and we
  want the columns to appears in the order given by the arguments. Last but not least: in
  `add_list_resource_command` we actually reimplement `filter_keys` in order to remove columns that
  should never be rendered (node._api for instance). First because we don't want users to display
  them, and second because PrettyTable take in account the rendering of hidden columns to calculate
  the height of each cells, which would produce very high columns in some cases.

- Allow to configure proxy certificate and key with one unique command
  ([`3b2571d`](https://github.com/enix/pvecontrol/commit/3b2571da998c38fa629763163eb91899a1a58edb))

- Enable outputFormats (yaml, json) for clusterstatus
  ([`eb9262a`](https://github.com/enix/pvecontrol/commit/eb9262ae02dd01684675bce88e4612500f180f0f))

- Support for proxmox clusters behind a reverse proxy with certificate-based authentication
  ([`902c759`](https://github.com/enix/pvecontrol/commit/902c759a1c31dd151df876169983312579dc3224))

- **cli**: Get --cluster flag from env
  ([`760c613`](https://github.com/enix/pvecontrol/commit/760c6135c72ecb2007ce7649ec9ace995a7c7526))

- **sanitycheck**: Check if disks are unused
  ([`d31752f`](https://github.com/enix/pvecontrol/commit/d31752f1420484515ba4a2a418ac5e716cdc6a07))

- **sanitycheck**: Check vms have a backup job configured
  ([`1b8617f`](https://github.com/enix/pvecontrol/commit/1b8617f9cf13aa0cc658376dfba0909e0b4c44d9))

- **sanitycheck**: Check vms have at least one recent backup
  ([`db42367`](https://github.com/enix/pvecontrol/commit/db42367a0290eccb4b40e53dcbe400ab56274b33))

- **sanitychecks**: Check onboot vm option
  ([`cda70f8`](https://github.com/enix/pvecontrol/commit/cda70f8c1a3e8ef8b04e6c083b19c8925a181cdc))

- **vm**: Parse tags as sets for easier usage
  ([`7dda4fe`](https://github.com/enix/pvecontrol/commit/7dda4fe3e19ec3ad3e461909a0b65f43accfcd6c))

### Refactoring

- Add PVEVolume and PVEBackupJob classes
  ([`f488dbe`](https://github.com/enix/pvecontrol/commit/f488dbe62a68042cfa0fb647a942152e50c41ae8))

- Create a click ResourceGroup class that automatically adds a list subcommand
  ([`592b6d0`](https://github.com/enix/pvecontrol/commit/592b6d0941a81106f7419a61be37fa28cca4218b))

- Move backups and backups_job listing in PVECluster and PVEVm
  ([`2cedc7d`](https://github.com/enix/pvecontrol/commit/2cedc7dc759601d4918bd51ed26eb0516836fe02))

- Move cli related functions from utils.py to cli.py
  ([`67cc27a`](https://github.com/enix/pvecontrol/commit/67cc27a2ade021ae696ccd49366992d54e6323d9))

- Move PVECluster.get_node_resources to PVENode.resources property
  ([`5f028ad`](https://github.com/enix/pvecontrol/commit/5f028adf0f71dc1a54dcf15d7b33f82d10f95fac))

- Remove dead code in Check
  ([`2a24f61`](https://github.com/enix/pvecontrol/commit/2a24f6124ffc62bfd8f91467057d57d9ab753d28))

- Use property instead of method whenever possible in PVECluster and PVENode
  ([`34efd0c`](https://github.com/enix/pvecontrol/commit/34efd0c51cff3286f1d8f92784dfbbcac767cc57))

- **cli**: Show help instead of an error when no args is provided
  ([`4d2d474`](https://github.com/enix/pvecontrol/commit/4d2d474ea56da6b7f7c44e67b80e305bdc9b9ccd))

- **cli**: Split subcommands between name and verb and use click instead of argparse
  ([`38f28f9`](https://github.com/enix/pvecontrol/commit/38f28f9633a09f79c369b1f17791db2982c3566a))

Co-authored-by: Yoann Lamouroux <yoann.lamouroux@enix.fr>

- **sanitycheck**: Improve vm_backups wording
  ([`1ca8721`](https://github.com/enix/pvecontrol/commit/1ca8721b0d008e3b249a12be061585445d767d7d))

- **sanitycheck**: Use storage.images instead of storage.get_content("images")
  ([`aa6db96`](https://github.com/enix/pvecontrol/commit/aa6db969ab8fab661f939cfe60bd526ef0aae6e9))

### Testing

- **sanitycheck**: Vm backups
  ([`5e0fd4e`](https://github.com/enix/pvecontrol/commit/5e0fd4e9d6a5676470de8ee7513742bb9bfe475d))


## v0.5.0 (2025-01-30)

### Bug Fixes

- Cleanup code
  ([`992d6d2`](https://github.com/enix/pvecontrol/commit/992d6d266196b86a946ef2af275189de5013300b))

- Correct clusterconfig default value overwrite
  ([`aa30cbf`](https://github.com/enix/pvecontrol/commit/aa30cbf48f52cdb44b901dcf1f719943b7143d7a))

- Crash on sortby None (default value)
  ([`075761e`](https://github.com/enix/pvecontrol/commit/075761ecdb7a879197ade4c061e683c4b61f7622))

- Crash when filtering returns 0 results
  ([`57c6892`](https://github.com/enix/pvecontrol/commit/57c68929bc93191f1b1b17984623ea090dbb7d40))

- Harmonize logs when using --wait and --follow
  ([`81df66a`](https://github.com/enix/pvecontrol/commit/81df66aca8cf664046832849aa0ced1e275607b5))

- Missing method self._initstatus() in task.refresh()
  ([`a730fc4`](https://github.com/enix/pvecontrol/commit/a730fc4de142f0bb215da15f9b5fdb20827ab5a8))

- Patch clusterconfig never set to default config
  ([`9d02b41`](https://github.com/enix/pvecontrol/commit/9d02b41befd0b5da09a919db7a6bb116573dddf6))

- Strenum isn't available for python 3.10
  ([`29e44bd`](https://github.com/enix/pvecontrol/commit/29e44bdc31a75eafc30bfeb1ae13c1a92826d8c3))

- Transpose existing sanity checks to new class
  ([`368d868`](https://github.com/enix/pvecontrol/commit/368d8680928ed97286c0842b656bb39b67099939))

- **clusterstatus**: Update cli output
  ([`23d3aa7`](https://github.com/enix/pvecontrol/commit/23d3aa722f75d50e0c3ec86fec53580c082cd2a4))

- **config**: Correct PVECluster args node to config
  ([`833dd6e`](https://github.com/enix/pvecontrol/commit/833dd6ec51cdd664d2d5b160660097f19c3eb1ec))

- **config**: Correct PVECluster args node to config
  ([`e5367e8`](https://github.com/enix/pvecontrol/commit/e5367e8aa478bb3c350bcf3c58e7ca0aa4df1b8b))

- **config**: Rollback node_factors to node
  ([`8dffbc8`](https://github.com/enix/pvecontrol/commit/8dffbc897148375ec6ad83103135454cff66b116))

- **evacuate**: Change log output
  ([`c2c4fd8`](https://github.com/enix/pvecontrol/commit/c2c4fd8b6573044b149706161293150574aa9671))

- **evacuate**: Make sure targets are unique
  ([`3627ef7`](https://github.com/enix/pvecontrol/commit/3627ef72658eca65c0587315bedd2fc1826b7ae0))

- **sanitycheck**: In VM config, cpu are not always return by API
  ([`842a444`](https://github.com/enix/pvecontrol/commit/842a44471dc7935ca73bf4e5cbb438d9eb0c21bf))

- **sanitycheck**: Patch error on if statements in ha_vms check
  ([`9030ffe`](https://github.com/enix/pvecontrol/commit/9030ffead30d8075598e7df19d09a3765ea96ebd))

- **sanitycheck**: Patch no checks append to sanity checks list
  ([`b280650`](https://github.com/enix/pvecontrol/commit/b280650174ac7f13cafee28a18d15e8888526bf3))

- **sanitycheck**: Verify check exists before trying to run it
  ([`1535772`](https://github.com/enix/pvecontrol/commit/15357720ae7a69b57b0ab8110955e67746df3999))

- **sanitychecks**: Add exitcode and correct message criticity code
  ([`ada9222`](https://github.com/enix/pvecontrol/commit/ada9222cf28516e8098cdd2713c7a159ac344704))

- **sanitychecks**: Add terminal supports verification (utf-8, bold, colors)
  ([`b37570a`](https://github.com/enix/pvecontrol/commit/b37570ac20a353f1f4a0a729f0b384ef614e3b6f))

- **sanitychecks**: Correct check code for ha_group
  ([`723a3e6`](https://github.com/enix/pvecontrol/commit/723a3e6f56a950d91e7f6724824576de08f388f4))

- **sanitychecks**: Patch display issues depending on terminal using curses
  ([`b8d1b04`](https://github.com/enix/pvecontrol/commit/b8d1b048faeeed73b54146d4dfa9cb8ae3ef3651))

- **sanitychecks**: Patch display issues depending on terminal using curses
  ([`b83e6e7`](https://github.com/enix/pvecontrol/commit/b83e6e798cacb641738b75c2c6986ccff1c0fb67))

- **sanitychecks**: Patch some issues
  ([`31ef892`](https://github.com/enix/pvecontrol/commit/31ef892d5ed2efbcdfd9943a8253bcff42db3c76))

- **sanitychecks**: Refacto Checks run with classes
  ([`2de9331`](https://github.com/enix/pvecontrol/commit/2de933116ab5e08902dfb5c395f05ced91782443))

- **storage**: Patch error on PVEStorage.__str__
  ([`8a83370`](https://github.com/enix/pvecontrol/commit/8a83370655ea10fd8363b9dc3377feda6766cdc7))

- **storagelist**: Add sort-by arg
  ([`0da34d4`](https://github.com/enix/pvecontrol/commit/0da34d4f9ae125dc2f3b18588feab9dfab9120bd))

- **storagelist**: Correct shared col
  ([`0d78b7f`](https://github.com/enix/pvecontrol/commit/0d78b7f153b1098e2ef2c891fd8f0ed08cd15496))

- **storagelist**: Prototype of print_tableoutput has changed
  ([`b5d4367`](https://github.com/enix/pvecontrol/commit/b5d43673b3d55502bb08ded47a325b2d423a8ae6))

- **storagelist**: Update PVEStorage kwargs loading
  ([`496118d`](https://github.com/enix/pvecontrol/commit/496118defc011b788b371d2a2452ddfafaf0659b))

- **tasks**: Nicely handle vanished tasks
  ([`64a1c4c`](https://github.com/enix/pvecontrol/commit/64a1c4c70c9ef08ad8fdb78be90f5126d34216d9))

Some tasks can deseappear from the API with time. So we must handle this case.

### Chores

- Add CI job for black and config in pyproject
  ([`d08192b`](https://github.com/enix/pvecontrol/commit/d08192babe9e6196b232922ea1f0c891c0232bbf))

- Fix ci cancelled jobs
  ([`61d6607`](https://github.com/enix/pvecontrol/commit/61d660763ef722d0d5ebaafbbee28d3cf7cc2868))

- Optimize cli by reducing HTTP calls
  ([`078c37d`](https://github.com/enix/pvecontrol/commit/078c37d698a222afff53493bf2d0fce7ec262c0f))

- Remove Github deployment in CI stage tests
  ([`5ee2257`](https://github.com/enix/pvecontrol/commit/5ee22570823172116a1d48526982418653661f85))

- Remove Github deployment in CI stage tests
  ([`a95bd61`](https://github.com/enix/pvecontrol/commit/a95bd614559d2a009d851418b4fec644e06e2c97))

- Run black
  ([`ef4be01`](https://github.com/enix/pvecontrol/commit/ef4be01563d4f7a6016b2c3d04a1dadf2a411efd))

- Run black
  ([`9aa757b`](https://github.com/enix/pvecontrol/commit/9aa757b54c0aa9d1e49887cd8d58c9e5b093ff6b))

- **auth**: Patch tests and lint
  ([`8b3d837`](https://github.com/enix/pvecontrol/commit/8b3d837b4a6ed65463686e8c4ddff888c98736dc))

- **black**: Correct style for sanitycheck
  ([`27b3c73`](https://github.com/enix/pvecontrol/commit/27b3c73c561d5e31dc27eb6b2697baa529e97151))

- **black**: Patch black warnings
  ([`bb17d7b`](https://github.com/enix/pvecontrol/commit/bb17d7b298341bfe47b94eb0f1a61ed895dcf619))

- **ci**: Fix CI execution for PRs
  ([`197c49f`](https://github.com/enix/pvecontrol/commit/197c49f35186c134f6e81a06f5ea8da2d1e71f32))

- **ci**: Update file requirements-dev.txt
  ([`13a540c`](https://github.com/enix/pvecontrol/commit/13a540cf0f18d4f38a202ed4ebc5f3e22878f551))

- **pylint**: Add CI job for pylint
  ([`579b436`](https://github.com/enix/pvecontrol/commit/579b4362f950fd5a8269499ee1907de24d3042c0))

- **pylint**: Init pylint refacto
  ([`2daa821`](https://github.com/enix/pvecontrol/commit/2daa82188abe6185bd1beeea7403a50551aa8a16))

- **pylint**: Patch last needed
  ([`0d87cde`](https://github.com/enix/pvecontrol/commit/0d87cdee065bdbe5cef0dd6bd7e39f5a26ab9678))

- **pylint**: Patch loop on pvecontrol module
  ([`a218711`](https://github.com/enix/pvecontrol/commit/a218711a7af675fed3a3b64a76544196af8b9d3c))

- **pylint**: Patch pvecontrol/actions/cluster.py
  ([`77725cb`](https://github.com/enix/pvecontrol/commit/77725cbf4460c8edda2189b209f859c7312dbc79))

- **pylint**: Patch pvecontrol/actions/storage.py
  ([`97a12c7`](https://github.com/enix/pvecontrol/commit/97a12c70d621574b58086178d041dbfb0b4e3469))

- **pylint**: Patch pvecontrol/actions/task.py
  ([`9332e6b`](https://github.com/enix/pvecontrol/commit/9332e6bf9a67ea74c771739d3a3020152fb83aa8))

- **pylint**: Patch pvecontrol/actions/vm.py
  ([`611afb7`](https://github.com/enix/pvecontrol/commit/611afb71a9b4632407d270eb92b9b6c8bcbe00f0))

- **pylint**: Patch pvecontrol/node.py
  ([`5f27f0b`](https://github.com/enix/pvecontrol/commit/5f27f0b989b2b4529f3879fea3151379e70c6ac5))

- **pylint**: Patch src/pvecontrol/cluster.py
  ([`17bb25e`](https://github.com/enix/pvecontrol/commit/17bb25e1b7d01b5c9c5608918738cc5869ff6796))

- **pylint**: Patch src/pvecontrol/storage.py
  ([`363b079`](https://github.com/enix/pvecontrol/commit/363b079fbbea4a803a4cde86679d2e3fc4c4cd5e))

- **pylint**: Patch src/pvecontrol/utils.py
  ([`8b76209`](https://github.com/enix/pvecontrol/commit/8b76209d118ea7d91b377f237f6ae6d75972841a))

- **pylint**: Patch typo
  ([`8353a7e`](https://github.com/enix/pvecontrol/commit/8353a7ebe44e3d412e4b570e6d0d8655537833f7))

- **pylint**: Rebase to branch black
  ([`2c60f5e`](https://github.com/enix/pvecontrol/commit/2c60f5ee7d300f4fff0765f5d219d1bb6c71a01a))

- **pylint**: Remove unnecessary pylint comment
  ([`d902a2e`](https://github.com/enix/pvecontrol/commit/d902a2ef137a26292cf064cb0353f687e6ba33a8))

- **README**: Add documentation about shell auto completion
  ([`2695418`](https://github.com/enix/pvecontrol/commit/26954187421b3be93aa947e4cbade4dd00e6b3e9))

- **README**: Complete doc for release
  ([`c8143c2`](https://github.com/enix/pvecontrol/commit/c8143c28f0787c340a2f28b63464cf888752edb7))

* docs: update README

* chore(README): Add token auth to documentation.

* docs: merge my token auth docs

---------

Co-authored-by: Laurent Corbes <laurent.corbes@enix.fr>

- **README**: Fix missing newline
  ([`d091473`](https://github.com/enix/pvecontrol/commit/d09147347dd76faf2594a090b8f3d0b8a15a6d92))

- **README**: Fix title
  ([`16eedc4`](https://github.com/enix/pvecontrol/commit/16eedc40c6798676363a21931ae7e928b1e8688d))

- **README**: With pylint modification dev command was updated
  ([`305759c`](https://github.com/enix/pvecontrol/commit/305759ce51961bde3dcdfb25265268f49d794c2c))

### Features

- --columns flag
  ([`2397102`](https://github.com/enix/pvecontrol/commit/239710200aabbdfb642104eee134be993f1d101b))

- Add --filter flag to node, task and vm
  ([`4dfbb52`](https://github.com/enix/pvecontrol/commit/4dfbb527593e5e84d66ec68723d268bc0fb977d4))

- Add --output option to list commands (supports text, json, csv and yaml)
  ([`c1ee523`](https://github.com/enix/pvecontrol/commit/c1ee5233034f86baa4c62acea9a0a16da9c69515))

- Add --sort-by flag
  ([`0a0cf4d`](https://github.com/enix/pvecontrol/commit/0a0cf4dc12103a00a74e1f5204afcad69922ae18))

- Add completion generation
  ([`3a38437`](https://github.com/enix/pvecontrol/commit/3a384374bf1dcd48abc7eccf1740170b1e7eea80))

- Add sanitycheck VM has HA disks
  ([`bcf535a`](https://github.com/enix/pvecontrol/commit/bcf535a174efee7d13242f80d31472174793f6d2))

- Add sanitycheck VM has HA disks
  ([`2722de8`](https://github.com/enix/pvecontrol/commit/2722de87f531da115e3a8a1ffdee2e409dabde90))

- Add shell-like globbing on nodeevacuate --target flag
  ([`d7b3393`](https://github.com/enix/pvecontrol/commit/d7b3393ace577c14ac24cfd72064b01e935d1fe9))

based on fnmatch.fnmatchcase from python stdlib

- Add support for authentication tokens
  ([`7a913a8`](https://github.com/enix/pvecontrol/commit/7a913a8181383c016b4839088f0f74949a0e34f1))

- Columns name validation (--sort-by & --filter flags)
  ([`7cd0bdb`](https://github.com/enix/pvecontrol/commit/7cd0bdb94d41f600dc1ac8cca1b623715fa3204b))

- Implement cpufactor and memoryminimum by cluster
  ([`bab64bf`](https://github.com/enix/pvecontrol/commit/bab64bf302c82d7c73b24b7db2ecc11c55cff136))

- **auth**: Add some checks on token auth
  ([`4394cde`](https://github.com/enix/pvecontrol/commit/4394cdec2d140d2f03c2cc519241cb5182a9d870))

- **auth**: Allow command on user, password config attributes
  ([`c628f96`](https://github.com/enix/pvecontrol/commit/c628f96c7a4d860560f2c2be85820e46e3ce363a))

- **auth**: Allow command on user, password config attributes
  ([`ffe12dc`](https://github.com/enix/pvecontrol/commit/ffe12dc3a04bbf60bdf593754b06eb698a165968))

- **auth**: Allow command on user, password config attributes
  ([`92cf67d`](https://github.com/enix/pvecontrol/commit/92cf67d45cb316b981fcbb71b902bd5e5820e8d2))

- **auth**: Update README.md
  ([`01ca6fe`](https://github.com/enix/pvecontrol/commit/01ca6fecbd2fe8624111022fcdcb9c0fce728414))

- **node**: Nodeevacuate add --wait flag
  ([`edae9da`](https://github.com/enix/pvecontrol/commit/edae9da4db0d7678f85b6f9d1a165585fe76c936))

- **sanitycheck**: Check HA VM has cpu type != host
  ([`d5c7d1f`](https://github.com/enix/pvecontrol/commit/d5c7d1f0b7870818eed68aa334ad431af2cb17b2))

- **sanitycheck**: Rewrite logic to run tests
  ([`c8153c9`](https://github.com/enix/pvecontrol/commit/c8153c9fac5d991ff66aff909cbfe31dfd171eb9))

- **sanitychecks**: Add colors support on ASCII icons
  ([`e8097c9`](https://github.com/enix/pvecontrol/commit/e8097c92d72ea993fe99b915df6a0d726b3eaf1b))

- **storagelist**: Add missing --filter flag
  ([`4d644fd`](https://github.com/enix/pvecontrol/commit/4d644fde98e2f8fe260509bc0ecb5de0ece8e8ea))

- **storagelist**: Add storages list group shared by storage name
  ([`361fc39`](https://github.com/enix/pvecontrol/commit/361fc39ec95ecbfc581ad05d78e2ea210c121192))

- **tasks**: Taskget add --wait flag
  ([`011db78`](https://github.com/enix/pvecontrol/commit/011db785d9a47ff33a25ff02ba56c969f0b06a98))

- **vm**: Vmmigrate add --wait flag
  ([`8b8f1f1`](https://github.com/enix/pvecontrol/commit/8b8f1f1f8dd0f48a45516f41507b83a2f5963f5d))

### Refactoring

- Default values of PVE objects (node, vm & task)
  ([`4ca64ea`](https://github.com/enix/pvecontrol/commit/4ca64eaa4dfdce67c3d384901cd2db1a0e46e101))

- Move tests in src directory
  ([`98755da`](https://github.com/enix/pvecontrol/commit/98755da38f83ef3ef1daed953edfbdfa816699c2))

- Simplify print_task
  ([`c65104f`](https://github.com/enix/pvecontrol/commit/c65104fc30cba247f00bb218665ae47a498a753e))


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
