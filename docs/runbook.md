# Conception — `pvecontrol runbook`

Document de conception de la feature « runbook » : dérouler une liste de commandes `pvecontrol`
décrite dans un fichier.

Ce document est destiné à être exécuté par étapes, éventuellement par plusieurs personnes ou
agents. Chaque tâche est identifiée (`T<étape>.<n>`), autonome, et porte ses critères
d'acceptation. Les dépendances entre tâches sont explicites.

Statut : conception validée, implémentation non démarrée.
Livraison : une branche et une PR par étape, cf. §7.

**Cycle de vie de ce fichier.** Le §3 (état des lieux) et le §7 (tâches) sont transitoires : ils
périment au fur et à mesure de l'implémentation, et seuls la ligne « Statut » et l'avancement des
tâches sont à maintenir d'ici là. Le §4 (architecture) et le §5 (format) sont durables. À la PR
finale de l'étape 3, le §5 est absorbé par le README (T4.1), le §4 devient une section
d'architecture (`CLAUDE.md` ou `docs/architecture.md`), et ce fichier est supprimé — pour ne pas
laisser dans `docs/` une spec figée que personne ne mettra à jour.

---

## 1. Objectif

Permettre de décrire dans un fichier versionnable une suite d'opérations `pvecontrol`
(migration, évacuation, contrôles) et de la dérouler de manière reproductible, avec un mode
simulation, des variables, et un compte rendu exploitable.

Cas d'usage principal : une maintenance d'hyperviseur, aujourd'hui exécutée à la main commande
par commande, devient un fichier relu et validé à l'avance puis déroulé.

### Hors périmètre (décidé)

Ces points sont volontairement écartés de cette feature. Ils ne doivent pas être implémentés
« en passant », mais l'architecture ne doit pas les rendre impossibles :

- **Génération de plans par les commandes** (`node evacuate --emit-plan`, workflow plan/apply à
  la terraform). La feature déroule un runbook *écrit à la main*. Le terme « plan » reste réservé
  à cet usage futur, cf. §2.
- **Reprise après échec** (fichier d'état, `--resume`, `--start-at`).
- **Assertions / conditions entre étapes** (`when:`, « attendre que le nœud soit vide »). Note :
  une forme dégradée est acquise gratuitement, cf. §6.5.
- **Boucles** (`for_each:`), parallélisme, branchements.
- **Identifiants d'étape (`id:`)** : les étapes sont adressées par leur index, cf. §6.7. Un `id:`
  stable serait indispensable à un `--resume`, lui-même hors périmètre.

---

## 2. Décisions retenues

| Sujet | Décision | Raison |
|---|---|---|
| Format | YAML, chaque étape porte une ligne en syntaxe CLI dans `run:` | Pas de surface CLI à maintenir en double ; métadonnées par étape possibles |
| Moteur | Refactor d'une couche métier `operations/`, appelée par click *et* par le runner | Résultats structurés, testables, pas de dépendance à `CliRunner` pour le métier |
| Rôle de click | Parseur, plus seulement exécuteur | Donne gratuitement la validation statique des étapes (`runbook validate`) |
| MVP | `--dry-run` global + variables/templating | Le reste (reprise, assertions) est reporté |
| Nom | `runbook`, groupe de commandes `runbook show\|validate\|run` | Terme métier exact ; « plan » désigne déjà une préparation calculée, y compris dans le code (`src/pvecontrol/actions/node.py:73`) |
| Adressage des étapes | Index 1-based, exposé par une option unique `--steps SPEC` | Suffisant pour la mise au point, seul usage visé ; une option au lieu de deux (`--only` + `--stop-after`) |
| Confirmations | Mode non interactif global (`--yes` sur le groupe racine), cf. §4.4 | Un seul mécanisme au lieu d'une injection de `--force` par commande ; profite aussi au scripting shell |
| Emplacement des fichiers | Chemin de fichier explicite uniquement | Aucune règle de résolution implicite ; un répertoire conventionnel reste ajoutable plus tard sans casse |
| Templating | `string.Template` (`${var}`), pas jinja2 | Zéro dépendance nouvelle ; interdit d'introduire de la logique dans un runbook |

---

## 3. État des lieux du code

Constats issus de la lecture du code, qui conditionnent le découpage. À vérifier avant de
commencer si le code a évolué depuis la rédaction.

> **Dépendance** : ces constats décrivent le code **avec** la branche `feat/vm-lock` (commande
> `vm unlock`) mergée, ce qui n'est pas encore le cas de `main` à la rédaction. T1.2 refactore
> précisément cette commande, et les numéros de ligne de `actions/vm.py` cités ci-dessous s'y
> rapportent. Cette PR doit donc être mergée avant le démarrage de l'étape 1.

### 3.1 La surface mutante est très réduite

Seuls quatre commandes modifient le cluster, et il n'existe que trois appels API mutants :

- `src/pvecontrol/models/vm.py:77` — `PVEVm.migrate()` → `POST .../migrate`
- `src/pvecontrol/models/vm.py:84` — `PVEVm.unlock()` → `PUT .../config`
- `src/pvecontrol/models/vm.py:90` — `PVEVm.create()` → `POST .../qemu`

Commandes concernées : `vm migrate`, `vm restore`, `vm unlock`, `node evacuate`. **Tout le reste
est en lecture seule** (`*/list`, `status`, `sanitycheck`, `report`, `task get`).

Conséquence majeure sur le découpage : la couche `operations/` n'a besoin d'exister que pour ces
quatre commandes. Les commandes de lecture n'en ont pas besoin — cf. T2.4.

### 3.2 Duplication de la migration

`src/pvecontrol/actions/vm.py:77` refait à la main l'appel `POST .../migrate` au lieu d'utiliser
`PVEVm.migrate()` (`src/pvecontrol/models/vm.py:72`), que `node evacuate` utilise lui
(`src/pvecontrol/actions/node.py:131`). Les deux implémentations divergent déjà légèrement dans
la construction des options. À dédupliquer en T1.1.

### 3.3 Chaque commande reconstruit le cluster

Toutes les commandes appellent `PVECluster.create_from_config()`
(`src/pvecontrol/models/cluster.py:67`), qui ouvre une connexion et fait un fetch complet
(`version`, `cluster/status`, `cluster/resources`, puis construction des nodes et storages).

Un runbook de 30 étapes ferait 30 connexions et 30 fetchs complets. Un cache process est un
**prérequis bloquant** (T0.3).

### 3.4 Les erreurs sortent par `sys.exit`

`src/pvecontrol/actions/vm.py` lignes 49, 54, 61, 115, 137, 159 ; `src/pvecontrol/actions/cluster.py:92`.
Le métier ne peut pas être appelé par un runner tant que ces sorties ne sont pas remplacées par
des exceptions (T0.1).

### 3.5 Deux commandes sont interactives

`input("Confirm (yes):")` dans `src/pvecontrol/actions/vm.py:145` (`vm unlock`) et
`src/pvecontrol/actions/node.py:121` (`node evacuate`). `vm unlock` a un `--force`,
`node evacuate` n'a aucun moyen d'être non interactif.

### 3.6 `sanitycheck` porte déjà un code de sortie

`src/pvecontrol/actions/cluster.py:92` fait `sys.exit(exitcode)` où `exitcode` vient de
`SanityCheck.run()`. C'est la brique qui donnera gratuitement des étapes bloquantes (§6.5).

### 3.7 Contrainte de test

Les tests patchent le point d'entrée du cluster, par exemple
`patch("pvecontrol.actions.vm.PVECluster.create_from_config", return_value=self.cluster)`
(`src/tests/test_vm.py:24`). Le cache de T0.3 doit donc vivre **à l'intérieur** de
`create_from_config`, pas dans un wrapper appelé à sa place, sinon toute la suite de tests casse.

### 3.8 Réutilisable tel quel

`get_leaf_command()` (`src/pvecontrol/__init__.py:18`) résout déjà une liste d'arguments en
(commande feuille, arguments restants) dans l'arbre click. C'est exactement ce dont le runner a
besoin (T3.2).

---

## 4. Architecture cible

Trois couches :

| Couche | Responsabilité | Interdits |
|---|---|---|
| `pvecontrol/actions/` | click : options, résolution du cluster, confirmation interactive, rendu | — |
| `pvecontrol/operations/` *(nouveau)* | métier : vérifications, appels API, retourne un résultat | `print`, `sys.exit`, `input` |
| `pvecontrol/models/` | objets Proxmox (inchangé) | — |

Le runner de runbook et la couche click appellent tous deux `operations/`. Aucun des deux n'appelle
l'autre.

### 4.1 Contrat d'une opération

```python
def migrate(cluster, vmid, target, *, online=False, dry_run=False) -> OperationResult
```

- Reçoit un `PVECluster` déjà construit (elle ne le construit jamais elle-même).
- Retourne un `OperationResult`.
- Lève une exception typée en cas d'échec (§4.3) ; ne retourne jamais un code d'erreur.
- Ne demande jamais confirmation : c'est l'appelant qui décide.

### 4.2 `OperationResult`

Dataclass, dans `pvecontrol/operations/__init__.py` (ou `pvecontrol/result.py`) :

```python
@dataclass
class OperationResult:
    status: OperationStatus   # OK | SKIPPED | DRY_RUN | FAILED
    message: str              # phrase destinée à l'utilisateur
    upid: str | None = None   # tâche Proxmox créée, le cas échéant
    data: dict = field(default_factory=dict)  # détails structurés
```

Sert à la fois au rendu des commandes (y compris `-o json`) et au récapitulatif du runbook.

### 4.3 Exceptions

Dans `pvecontrol/exceptions.py` :

```
PVEControlError            # base
├── NotFoundError          # VM, nœud, storage inexistant
├── PreconditionError      # nœud hors ligne, ressources insuffisantes, VM non verrouillée…
└── APIError               # erreur remontée par proxmoxer
```

- Couche click : attrape, log en `error`, `sys.exit(1)`.
- Runner : attrape, marque l'étape en échec, applique `on_error`.

### 4.4 Confirmation et mode non interactif

Les confirmations restent dans `actions/` — le métier ne prompte jamais (§4.1). Mais le runner
invoque les commandes click, donc il traverserait ces prompts. D'où un **mode non interactif
global** :

- Un flag `--yes` / `-y` est ajouté au groupe racine et transporté dans `ctx.obj["args"]`, comme
  `color` et `unicode` le sont déjà (`src/pvecontrol/__init__.py:98`).
- Toute confirmation de `actions/` le consulte avant de prompter. `vm unlock --force` est conservé
  en alias rétrocompatible ; `node evacuate`, qui n'a aujourd'hui aucun moyen d'être non
  interactif (`src/pvecontrol/actions/node.py:121`), en gagne un.
- **Le runner active toujours ce mode.** Sa propre confirmation unique au démarrage — l'affichage
  de toutes les étapes — remplace les prompts par étape. `runbook run --yes` saute cette
  confirmation-là.

Conséquence à documenter : la confirmation de `node evacuate` affiche une liste de migrations
calculée à l'exécution, qu'on ne peut donc pas montrer d'avance. En mode runbook, cette liste est
affichée mais pas soumise à confirmation. C'est le rôle de `--dry-run` (§6.4) de permettre de la
relire au préalable.

---

## 5. Spécification du format

### 5.1 Exemple de référence

```yaml
version: 1
name: Maintenance pve-03
cluster: fr-par-1
vars:
  node: pve-03
  target: pve-01
defaults:
  on_error: abort      # abort | continue
  wait: true
steps:
  - name: Santé du cluster avant intervention
    run: sanitycheck

  - name: Migrer la VM critique en premier
    run: vm migrate 100 --target ${target} --online

  - name: Vider le nœud
    run: node evacuate ${node} --online

  - name: Inventaire final
    run: node list --filter node ${node}
    on_error: continue
```

### 5.2 Schéma

Validé par `confuse`, comme le reste de la configuration (cf. `src/pvecontrol/config.py`).

| Clé | Niveau | Type | Défaut | Description |
|---|---|---|---|---|
| `version` | racine | int | — | Requis. Vaut `1`. Toute autre valeur est refusée. |
| `name` | racine | str | nom du fichier | Libellé du runbook |
| `cluster` | racine | str | `-c` de la CLI | Cluster par défaut des étapes |
| `vars` | racine | map str→str | `{}` | Variables substituables |
| `defaults` | racine | map | voir ci-dessous | Valeurs par défaut des étapes |
| `steps` | racine | liste | — | Requis, non vide |
| `name` | étape | str | résumé de `run` | Libellé affiché |
| `run` | étape | str | — | Requis. Ligne en syntaxe CLI. |
| `cluster` | étape | str | `cluster` racine | Surcharge par étape |
| `on_error` | étape | `abort`\|`continue` | `abort` | Comportement en cas d'échec |
| `wait` | étape | bool | `true` | Attendre la fin de la tâche Proxmox |

### 5.3 Règles sur `run`

1. **Pas d'options globales.** `-c/--cluster`, `-o/--output`, `--config`, `-d/--debug`,
   `--color`, `--unicode` sont **refusées** dans `run:` avec une erreur explicite. Le cluster
   est porté par la clé YAML `cluster:`, le reste par la ligne de commande `runbook run`. Éviter
   deux sources de vérité est le point le plus important de cette règle.
2. **Pas d'interprétation shell.** Découpage par `shlex.split` uniquement : pas de pipes, pas de
   redirections, pas de `$(...)`, pas de glob.
3. **`--wait` est injecté par le runner** quand `wait: true` et que la commande cible accepte
   cette option. Il n'est pas à écrire dans `run:`.

### 5.4 Substitution des variables

- Syntaxe `${nom}`, via `string.Template`.
- **La substitution s'applique après `shlex.split`, token par token.** Une valeur contenant un
  espace reste donc un seul argument, et une variable ne peut pas injecter d'options
  supplémentaires. Ne jamais substituer avant le découpage.
- Précédence : `--var nom=valeur` (CLI) > `vars:` (runbook). L'environnement n'est pas consulté.
- Une variable référencée mais non définie est une **erreur de validation**, pas une chaîne vide.
- Une variable définie et non utilisée déclenche un avertissement.

---

## 6. Spécification du runner

### 6.1 Surface CLI

```
pvecontrol runbook show FILE
pvecontrol runbook validate FILE [--var k=v]
pvecontrol runbook run FILE [--dry-run] [--yes] [--var k=v] [--on-error abort|continue] [--steps SPEC]
```

- `show` : tableau des étapes (n°, nom, commande résolue, cluster, on_error), via `print_output`,
  donc compatible `-o json|md|csv`. Le n° est celui défini au §6.7.
- `validate` : parse le YAML, substitue, résout et valide chaque étape via click. **Aucun appel
  API.** Code de sortie non nul si une étape est invalide.
- `run` : déroule. `--on-error` surcharge le `defaults.on_error` du fichier ; `--yes` saute la
  confirmation initiale (§4.4) ; `--steps` restreint l'exécution (§6.7).

`FILE` est un chemin de fichier, résolu par `click.Path(exists=True, dir_okay=False)`. Aucune
recherche implicite dans un répertoire conventionnel, aucune extension devinée (§8).

### 6.2 Cycle de vie d'une étape

1. `tokens = shlex.split(step.run)`
2. Substitution des variables token par token (§5.4)
3. Refus des options globales (§5.3 règle 1)
4. Résolution dans l'arbre click via `get_leaf_command()` (`src/pvecontrol/__init__.py:18`)
5. `cmd.make_context(...)` → click valide types, `required`, `Choice` → `UsageError` = étape invalide
6. *(`validate` s'arrête ici)*
7. Injection de `--wait` si applicable, et de `dry_run` si `--dry-run`
8. `cmd.invoke(ctx)` → la commande délègue à `operations/` et retourne un `OperationResult`
9. Si l'étape était mutante et a réussi : `cluster.refresh()` avant l'étape suivante

Les étapes 1 à 5 sont exécutées **pour toutes les étapes du runbook avant d'en lancer une seule**.
Un runbook dont la 7ᵉ étape a une faute de frappe ne doit pas s'arrêter au milieu après avoir migré
six VMs.

### 6.3 Rafraîchissement du cluster

`PVECluster.refresh()` (`src/pvecontrol/models/cluster.py:111`) refait tout (status, resources,
tasks, ha) : c'est coûteux. Il n'est appelé qu'après une étape **mutante réussie**, pas après une
étape de lecture ni en dry-run.

### 6.4 Dry-run

`--dry-run` propage `dry_run=True` à toutes les opérations. Ce n'est pas un simple affichage :
toutes les vérifications réelles sont exécutées (la VM existe, le nœud cible est en ligne, le
preflight `GET .../migrate` passe), seul l'appel mutant est sauté. Le résultat porte le statut
`DRY_RUN`.

**Limite à documenter dans le README** : en dry-run l'étape N+1 observe l'état d'avant l'étape N.
Un runbook qui migre une VM puis agit dessus sur son nouveau nœud remontera une fausse erreur.
Comportement retenu : en dry-run, `on_error` est forcé à `continue`, et un échec de précondition
est marqué `UNVERIFIABLE` (statut distinct de `FAILED`) dans le récapitulatif, avec une note
expliquant la cause probable.

### 6.5 Étapes bloquantes (acquis gratuitement)

Bien que les assertions soient hors périmètre, `sanitycheck` retourne déjà un code de sortie non
nul quand un contrôle échoue (§3.6). Avec `on_error: abort`, une étape `run: sanitycheck` suffit
donc à conditionner la suite du runbook à la santé du cluster. Ce comportement doit être préservé
par T2.3 et documenté comme le moyen recommandé de sécuriser un runbook.

### 6.6 Compte rendu

- Pendant l'exécution : une ligne par étape (n°, nom, statut, durée), sortie brute de la commande
  conservée. Format détaillé au §6.7.
- À la fin : tableau récapitulatif via `print_output` (n°, nom, statut, durée, upid, message),
  donc exploitable en CI avec `-o json`.
- Code de sortie de `runbook run` : `0` si toutes les étapes sont `OK`/`SKIPPED`/`DRY_RUN`, non nul
  dès qu'une étape est `FAILED` (y compris si `on_error: continue` a permis de poursuivre).

### 6.7 Numérotation des étapes et exécution partielle

Les étapes sont numérotées **1-based selon leur ordre dans `steps:`**. Ce numéro est le seul
moyen d'adresser une étape ; il n'existe pas de champ `id:` (cf. §1).

**Règle centrale : c'est le même numéro partout.** `show`, la progression pendant `run`, le
tableau récapitulatif final et les messages d'erreur de `validate` (« étape 3 : option inconnue
`--targt` ») désignent tous l'étape par ce numéro. Sans cette cohérence, `--steps` est
indevinable pour l'utilisateur.

Format de la progression pendant `run` :

```
[2/4] Migrer la VM critique en premier
      vm migrate 100 --target pve-01 --online
      … sortie de la commande …
      ✔ OK (12s) — UPID:pve-01:0000A1B2:…
```

`--steps SPEC` sélectionne les étapes à exécuter. `SPEC` accepte `3` (une étape), `2-4` (plage),
`3-` (jusqu'à la fin), `-2` (depuis le début) et une liste séparée par des virgules. Une valeur
hors bornes est une erreur, pas un avertissement.

Deux contraintes, qui sont l'essentiel de la tâche :

1. **Le numéro affiché ne change jamais avec le filtrage.** Avec `--steps 2`, on affiche `[2/4]`
   et non `[1/1]` : le dénominateur reste le nombre total d'étapes du runbook. Sinon la
   correspondance avec le fichier est perdue et l'option devient inutilisable.
2. **Les étapes non sélectionnées apparaissent en `SKIPPED`** dans le récapitulatif, qui reste
   donc aligné ligne à ligne sur le runbook.

Une exécution partielle est intrinsèquement risquée : l'étape 3 suppose en général que l'étape 2
a tourné. `run` affiche un avertissement explicite au démarrage — « exécution partielle : les
étapes 1-2 ne seront pas exécutées » — sans blocage supplémentaire, la confirmation initiale
existant déjà. La pré-validation du §6.2 reste intégrale : **toutes** les étapes du fichier sont
validées, y compris celles que `--steps` écarte.

---

## 7. Étapes et tâches

Les étapes sont séquentielles. À l'intérieur d'une étape, les tâches sont parallélisables sauf
dépendance indiquée.

### Stratégie de livraison

Stratégie **hybride** : les étapes de refactor vont directement dans `main`, la feature est isolée
sur une branche d'intégration.

| Étape | Branche | Part de | Merge vers | Contenu |
|---|---|---|---|---|
| 0 | `refactor/operations-socle` | `main` | `main` | exceptions, `OperationResult`, cache cluster |
| 1 | `refactor/operations-vm` | `main` | `main` | couche `operations/` pilote |
| 2 | `refactor/operations-node` | `main` | `main` | reste du périmètre + mode non interactif |
| 3 et 4 | `feat/runbook` *(intégration)* | `main` | `main`, en un seul merge | la commande, sa doc et ses exemples |

**Pourquoi ce partage.** Les étapes 0 à 2 touchent du code partagé (`actions/`, `models/`,
`cli.py`) : les garder hors de `main` pendant tout le projet accumulerait la divergence que le
découpage en étapes cherche justement à éviter. Elles ont en outre une valeur propre, indépendante
du runbook — déduplication de `migrate`, cache de cluster (gain sur *toutes* les commandes),
`--yes` global, `vm restore --dry-run` — et, étant en `refactor:`, elles ne publient rien.

L'étape 3 est isolée pour une raison précise : elle compte 9 tâches, et un `feat:` mergé dans
`main` au milieu publierait une commande `runbook` à moitié construite. Chaque T3.x part donc de
`feat/runbook` et y retourne ; l'étape 4 (doc, exemples, complétion) est réalisée sur la même
branche, pour que le merge final livre la commande *et* sa documentation d'un bloc.

**Merger, ne pas squasher, `feat/runbook` vers `main`.** Un squash écraserait les messages
granulaires en un seul commit et détruirait la traçabilité « quel changement a cassé quoi ». Avec
un vrai merge, les commits intermédiaires arrivent sur `main` et seul le `feat:` déclenche le bump.
Reporter `main` dans `feat/runbook` régulièrement, pas seulement à la fin.

Chaque PR doit être mergeable seule : `pytest` vert, `black . --check`, `pylint src/` (les trois
portes de `.github/workflows/tests.yml`), et **aucune régression de comportement CLI** pour les
étapes 0 à 2. `main` est protégée et impose une PR avec revue (README, section Contributing).

#### Conventions de commit et release automatique

`pyproject.toml` configure python-semantic-release avec `minor_tags = ["feat"]` et
`patch_tags = ["fix", "perf"]`. Autrement dit, **`refactor:`, `test:` et `chore:` ne publient
rien** : les étapes de refactor peuvent être mergées dans `main` sans déclencher de release, ce
qui est exactement l'effet recherché.

Corollaire à respecter : **ne pas employer `feat:` avant que la commande `runbook` existe**, sous
peine de publier une version qui annonce une feature absente. Les `feat:` de l'étape 3 vivent sur
`feat/runbook` et ne publient donc rien tant qu'elle n'est pas mergée ; c'est ce merge unique qui
déclenchera le bump mineur (0.8.0 → 0.9.0, `major_on_zero = false`).

Deux exceptions légitimes, parce qu'elles ajoutent une option visible et utile en soi :

- **T1.3** ajoute `vm restore --dry-run` → `feat(vm):`
- **T2.5** ajoute `--yes` global → `feat:`

#### Points de contrôle

- **Fin d'étape 1** : c'est la revue qui valide la forme du découpage en trois couches. Si elle ne
  convainc pas, seul `vm` est concerné — d'où le choix d'un pilote sur un seul module, et l'intérêt
  de trancher avant que la PR n'atteigne `main`.
- **Fin d'étape 2** : plus aucun `input()` ni `sys.exit` dans le métier, cache cluster actif sur
  toutes les commandes. Le runner de l'étape 3 ne devrait plus rien exiger de `actions/`.

Ce document est à committer en premier (`docs:`), afin que chaque branche d'étape parte d'un
`main` qui le contient.

### Étape 0 — Socle technique

Aucun changement visible pour l'utilisateur. Préalable à tout le reste.

**T0.1 — Exceptions typées**
Créer `src/pvecontrol/exceptions.py` avec la hiérarchie du §4.3. Ne rien migrer encore.
*Acceptation* : module créé, testé unitairement pour la hiérarchie, `pylint` propre.

**T0.2 — `OperationResult`**
Créer la dataclass et l'énumération de statuts du §4.2 (`OK`, `SKIPPED`, `DRY_RUN`,
`UNVERIFIABLE`, `FAILED`), avec un helper de rendu texte.
*Acceptation* : dataclass créée, sérialisable en dict pour `-o json`.

**T0.3 — Cache de cluster** *(prérequis bloquant, cf. §3.3)*
Mémoïser `PVECluster.create_from_config()` par nom de cluster, **à l'intérieur de la méthode**
(cf. contrainte de test §3.7). Prévoir une fonction de purge pour les tests.
*Acceptation* : deux appels successifs pour le même cluster ne produisent qu'une série de
requêtes HTTP (vérifiable avec `responses`) ; **toute la suite de tests existante passe sans
modification**.

### Étape 1 — Couche `operations`, pilote sur `vm`

C'est l'étape qui valide la forme du découpage. Elle doit être revue avant de lancer l'étape 2.

**T1.1 — `operations/vm.py: migrate()`** *(dépend de T0.1, T0.2)*
Extraire le métier de `src/pvecontrol/actions/vm.py:24-82`. **Dédupliquer avec
`PVEVm.migrate()`** (cf. §3.2) : une seule implémentation, celle du modèle, enrichie si besoin.
Ajouter `dry_run`.
*Acceptation* : `vm migrate` et `node evacuate` empruntent le même chemin de code ; comportement
CLI inchangé ; tests existants verts.

**T1.2 — `operations/vm.py: unlock()`** *(dépend de T0.1, T0.2)*
Extraire `src/pvecontrol/actions/vm.py:118-161`. La confirmation (`input`, ligne 145) **reste
dans `actions/`**. L'opération retourne `SKIPPED` si la VM n'est pas verrouillée.
*Acceptation* : `src/tests/test_vm.py` passe sans modification ; nouveau test unitaire appelant
l'opération sans `CliRunner`.

**T1.3 — `operations/vm.py: restore()`** *(dépend de T0.1, T0.2)*
Extraire `src/pvecontrol/actions/vm.py:85-116`. **Ajouter le `--dry-run` qui manque** à cette
commande, pour l'uniformité exigée par §6.4.
*Acceptation* : `vm restore --dry-run` n'émet aucune requête mutante mais valide ses préconditions.

**T1.4 — `actions/vm.py` devient une coquille** *(dépend de T1.1–T1.3)*
Ne conserver que : décorateurs click, résolution du cluster, confirmation, rendu du
`OperationResult`, traduction des exceptions en `sys.exit(1)`. Plus aucun `sys.exit` dans le
métier. Supprimer `_get_vm()` au profit de `PVECluster.get_vm()` (le `FIXME` de
`src/pvecontrol/actions/vm.py:164` le demande déjà).
*Acceptation* : aucun appel API dans `actions/vm.py` ; tests verts.

**T1.5 — Tests du métier sans `CliRunner`** *(dépend de T1.4)*
Ajouter `src/tests/test_operations_vm.py` : tests des trois opérations appelées directement,
y compris les chemins d'erreur (exceptions typées) et `dry_run`.
*Acceptation* : les chemins d'erreur sont couverts sans passer par click.

### Étape 2 — Reste du périmètre

**T2.1 — `operations/node.py: evacuate()`** *(dépend de l'étape 1)*
Extraire `src/pvecontrol/actions/node.py:24-137`. Séparer nettement le **calcul** de la liste des
migrations et son **exécution** : la fonction de calcul retourne la liste, `actions/` l'affiche et
demande confirmation, puis l'exécution est appelée. Ce découpage est aussi ce qui rendra possible
un futur `--emit-plan` (hors périmètre, mais ne pas le fermer).
*Acceptation* : la logique de sélection des cibles est testable unitairement sans `input()` ; le
comportement interactif de la CLI est inchangé.

**T2.2 — Uniformiser `wait`/`follow`** *(dépend de T2.1)*
`print_task()` (`src/pvecontrol/utils.py:160`) mélange attente et affichage. Extraire l'attente
(« bloquer jusqu'à la fin de la tâche ») de l'affichage, pour que le runner puisse attendre sans
imposer un format de sortie.
*Acceptation* : une fonction d'attente utilisable sans effet de bord d'affichage ; `task get -f/-w`
inchangé.

**T2.3 — `sanitycheck` retourne au lieu de sortir**
`src/pvecontrol/actions/cluster.py:92` : remonter le code via un `OperationResult`, la couche
click faisant le `sys.exit`. **Préserver le code de sortie actuel** (cf. §6.5).
*Acceptation* : `pvecontrol sanitycheck` conserve exactement son code de sortie ; utilisable comme
étape bloquante.

**T2.4 — Commandes de lecture : ne rien sur-refactorer**
Les `*/list` sont générées par `add_list_resource_command()` (`src/pvecontrol/cli.py:93`) et
`status`/`report` sont en lecture seule. **Elles ne reçoivent pas de couche `operations/`.**
Seule vérification attendue : elles bénéficient du cache T0.3 et ne font aucun `sys.exit` en
dehors d'une erreur réelle.
*Acceptation* : décision documentée dans le code ; aucune régression.

**T2.5 — Mode non interactif global** *(dépend de T1.2, T2.1)*
Ajouter `--yes` / `-y` au groupe racine (`src/pvecontrol/__init__.py:98`), le transporter dans
`ctx.obj["args"]`, et le faire consulter par les deux confirmations existantes
(`src/pvecontrol/actions/vm.py:145`, `src/pvecontrol/actions/node.py:121`). Implémenter §4.4.
Conserver `vm unlock --force` en alias.
*Acceptation* : `node evacuate --yes` s'exécute sans prompt ; `vm unlock --force` inchangé ;
aucune commande ne peut plus bloquer sur `input()` quand le mode est actif.

### Étape 3 — Le runner

**T3.1 — Schéma et parsing du runbook** *(dépend de l'étape 2)*
`src/pvecontrol/runbook/model.py` : chargement YAML, validation confuse du schéma §5.2, messages
d'erreur pointant la ligne/étape fautive.
*Acceptation* : runbook malformé → message explicite désignant l'étape ; `version` inconnue refusée.

**T3.2 — Résolution des étapes** *(dépend de T3.1)*
`src/pvecontrol/runbook/resolver.py` : `shlex.split`, refus des options globales (§5.3), résolution
via `get_leaf_command()`, `make_context()`.
*Acceptation* : une commande inexistante, une option inconnue ou un argument manquant sont
détectés sans aucun appel API.

**T3.3 — Substitution des variables** *(dépend de T3.2)*
Implémenter §5.4. **Substitution par token, après découpage.**
*Acceptation* : test dédié prouvant qu'une variable valant `a b --force` produit un unique
argument et n'injecte pas d'option ; variable non définie = erreur.

**T3.4 — `runbook show`** *(dépend de T3.3)*
Première colonne = le n° d'étape du §6.7.

**T3.5 — `runbook validate`** *(dépend de T3.3)*
Les erreurs désignent l'étape par son n° (§6.7).
*Acceptation* : sur un runbook valide, zéro requête HTTP (vérifiable avec `responses`).

**T3.6 — `runbook run`** *(dépend de T3.3, T2.2)*
Séquencement, pré-validation intégrale avant exécution (§6.2), `on_error`, injection de `--wait`,
`refresh()` conditionnel (§6.3), confirmation initiale et `--yes`.
*Acceptation* : une faute de frappe en étape 7 empêche l'exécution de l'étape 1 ; `on_error:
continue` poursuit mais le code de sortie final reste non nul.

**T3.7 — `--dry-run` global** *(dépend de T3.6)*
Implémenter §6.4, y compris le statut `UNVERIFIABLE` et le forçage de `on_error: continue`.

**T3.8 — Compte rendu** *(dépend de T3.6)*
Implémenter §6.6.
*Acceptation* : `runbook run -o json` produit un document exploitable en CI.

**T3.9 — `--steps SPEC`** *(dépend de T3.6, T3.8)*
Parsing de `SPEC` (`3`, `2-4`, `3-`, `-2`, listes), avertissement d'exécution partielle,
étapes écartées marquées `SKIPPED`. Implémenter §6.7.
*Acceptation* : `--steps 2` sur un runbook de 4 étapes affiche `[2/4]` et non `[1/1]` ; la
pré-validation porte toujours sur les 4 étapes ; une valeur hors bornes est une erreur.

### Étape 4 — Documentation et finitions

**T4.1 — README** : section `runbook`, format, variables, dry-run et sa limite (§6.4), usage de
`sanitycheck` comme garde-fou (§6.5).
**T4.2 — Exemples** : `examples/runbooks/` avec au moins un runbook de maintenance de nœud commenté.
**T4.3 — Complétion shell** : vérifier que `runbook` s'intègre à la complétion existante
(`_PVECONTROL_COMPLETE`), et compléter les chemins de fichiers pour `FILE`.

---

## 8. Décisions différées

Plus aucun point n'est ouvert : la conception est complète et l'implémentation peut démarrer.

Les éléments ci-dessous ont été écartés **en connaissance de cause**, et sont tous ajoutables plus
tard sans rupture de compatibilité. Ils sont listés ici pour qu'on n'ait pas à re-instruire le
sujet :

- **Répertoire conventionnel de runbooks.** `runbook run maintenance` chercherait dans
  `~/.config/pvecontrol/runbooks/`. Ajoutable via la règle « si l'argument n'est pas un chemin
  existant, le chercher dans le répertoire conventionnel », qui ne casse aucun usage antérieur.
- **Identifiants d'étape `id:`.** Cf. §1 et §6.7. `--steps` pourra les accepter avec la règle
  « si ça parse en entier, c'est un index, sinon c'est un id ».
- **Reprise après échec, assertions, boucles, génération de plans.** Cf. §1.

## 9. Références de code

| Sujet | Emplacement |
|---|---|
| Groupe racine click, options globales | `src/pvecontrol/__init__.py:98` |
| Résolution dans l'arbre click | `src/pvecontrol/__init__.py:18` |
| Enregistrement des commandes | `src/pvecontrol/__init__.py:191` |
| Génération des commandes `list` | `src/pvecontrol/cli.py:93` |
| Construction du cluster | `src/pvecontrol/models/cluster.py:67` |
| Rafraîchissement du cluster | `src/pvecontrol/models/cluster.py:111` |
| Appels API mutants | `src/pvecontrol/models/vm.py:77,84,90` |
| Migration dupliquée | `src/pvecontrol/actions/vm.py:77` |
| Confirmations interactives | `src/pvecontrol/actions/vm.py:145`, `src/pvecontrol/actions/node.py:121` |
| Code de sortie `sanitycheck` | `src/pvecontrol/actions/cluster.py:92` |
| Attente/affichage de tâche | `src/pvecontrol/utils.py:160` |
| Schéma de configuration | `src/pvecontrol/config.py:5` |
| Harnais de test | `src/tests/testcase.py`, `src/tests/test_vm.py:24` |
