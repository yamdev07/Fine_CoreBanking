"""
Définitions des plans comptables standards.

PCIMF  — Plan Comptable des Institutions de MicroFinance (BCEAO/UEMOA)
PCEC   — Plan Comptable des Établissements de Crédit (Banques Commerciales BCEAO)
CUSTOM — Aucun compte pré-chargé, l'institution construit son propre plan
"""
from dataclasses import dataclass, field

from app.models.accounting import AccountClass, AccountNature, AccountType


@dataclass
class AccountDef:
    code: str
    name: str
    account_class: AccountClass
    account_type: AccountType
    account_nature: AccountNature
    parent_code: str | None = None
    is_leaf: bool = True
    allow_manual_entry: bool = True


@dataclass
class PlanTemplate:
    id: str
    name: str
    description: str
    target: str           # "MICROFINANCE" | "BANK" | "CUSTOM"
    accounts: list[AccountDef] = field(default_factory=list)
    journal_codes: list[dict] = field(default_factory=list)


# ─── PCIMF — Microfinance ─────────────────────────────────────────────────────

PCIMF_ACCOUNTS: list[AccountDef] = [
    # Classe 1 — Capitaux propres
    AccountDef("1",      "CAPITAUX PROPRES",                  AccountClass.CAPITAL,    AccountType.PASSIF,  AccountNature.CREDITEUR, is_leaf=False),
    AccountDef("10",     "Capital et dotations",              AccountClass.CAPITAL,    AccountType.PASSIF,  AccountNature.CREDITEUR, "1",   is_leaf=False),
    AccountDef("101000", "Capital social",                    AccountClass.CAPITAL,    AccountType.PASSIF,  AccountNature.CREDITEUR, "10"),
    AccountDef("102000", "Parts sociales membres",            AccountClass.CAPITAL,    AccountType.PASSIF,  AccountNature.CREDITEUR, "10"),
    AccountDef("103000", "Dotations",                         AccountClass.CAPITAL,    AccountType.PASSIF,  AccountNature.CREDITEUR, "10"),
    AccountDef("11",     "Réserves",                          AccountClass.CAPITAL,    AccountType.PASSIF,  AccountNature.CREDITEUR, "1",   is_leaf=False),
    AccountDef("110000", "Réserve légale",                    AccountClass.CAPITAL,    AccountType.PASSIF,  AccountNature.CREDITEUR, "11"),
    AccountDef("111000", "Réserves facultatives",             AccountClass.CAPITAL,    AccountType.PASSIF,  AccountNature.CREDITEUR, "11"),
    AccountDef("12",     "Résultat de l'exercice",            AccountClass.CAPITAL,    AccountType.PASSIF,  AccountNature.CREDITEUR, "1",   is_leaf=False),
    AccountDef("120000", "Résultat net",                      AccountClass.CAPITAL,    AccountType.PASSIF,  AccountNature.CREDITEUR, "12"),
    AccountDef("13",     "Subventions et fonds affectés",     AccountClass.CAPITAL,    AccountType.PASSIF,  AccountNature.CREDITEUR, "1",   is_leaf=False),
    AccountDef("130000", "Subventions d'exploitation",        AccountClass.CAPITAL,    AccountType.PASSIF,  AccountNature.CREDITEUR, "13"),
    AccountDef("131000", "Fonds de garantie",                 AccountClass.CAPITAL,    AccountType.PASSIF,  AccountNature.CREDITEUR, "13"),

    # Classe 2 — Immobilisations
    AccountDef("2",      "ACTIFS IMMOBILISÉS",                AccountClass.IMMOBILISE, AccountType.ACTIF,   AccountNature.DEBITEUR,  is_leaf=False),
    AccountDef("21",     "Immobilisations corporelles",       AccountClass.IMMOBILISE, AccountType.ACTIF,   AccountNature.DEBITEUR,  "2",   is_leaf=False),
    AccountDef("211000", "Terrains",                          AccountClass.IMMOBILISE, AccountType.ACTIF,   AccountNature.DEBITEUR,  "21"),
    AccountDef("212000", "Constructions",                     AccountClass.IMMOBILISE, AccountType.ACTIF,   AccountNature.DEBITEUR,  "21"),
    AccountDef("213000", "Matériel et outillage",             AccountClass.IMMOBILISE, AccountType.ACTIF,   AccountNature.DEBITEUR,  "21"),
    AccountDef("218000", "Matériel informatique",             AccountClass.IMMOBILISE, AccountType.ACTIF,   AccountNature.DEBITEUR,  "21"),
    AccountDef("22",     "Immobilisations incorporelles",     AccountClass.IMMOBILISE, AccountType.ACTIF,   AccountNature.DEBITEUR,  "2",   is_leaf=False),
    AccountDef("221000", "Logiciels et licences",             AccountClass.IMMOBILISE, AccountType.ACTIF,   AccountNature.DEBITEUR,  "22"),

    # Classe 3 — Opérations interbancaires
    AccountDef("3",      "OPÉRATIONS INTERBANCAIRES",         AccountClass.STOCK,      AccountType.ACTIF,   AccountNature.DEBITEUR,  is_leaf=False),
    AccountDef("31",     "Comptes BCEAO",                     AccountClass.STOCK,      AccountType.ACTIF,   AccountNature.DEBITEUR,  "3",   is_leaf=False),
    AccountDef("311000", "Compte courant BCEAO",              AccountClass.STOCK,      AccountType.ACTIF,   AccountNature.DEBITEUR,  "31"),
    AccountDef("32",     "Refinancements reçus",              AccountClass.STOCK,      AccountType.PASSIF,  AccountNature.CREDITEUR, "3",   is_leaf=False),
    AccountDef("321000", "Refinancements IMF apex",           AccountClass.STOCK,      AccountType.PASSIF,  AccountNature.CREDITEUR, "32"),

    # Classe 4 — Opérations avec membres/clientèle
    AccountDef("4",      "OPÉRATIONS MEMBRES / CLIENTÈLE",    AccountClass.TIERS,      AccountType.ACTIF,   AccountNature.DEBITEUR,  is_leaf=False),

    # Crédits
    AccountDef("25",     "Crédits accordés",                  AccountClass.TIERS,      AccountType.ACTIF,   AccountNature.DEBITEUR,  "4",   is_leaf=False),
    AccountDef("251000", "Microcrédits individuels",          AccountClass.TIERS,      AccountType.ACTIF,   AccountNature.DEBITEUR,  "25"),
    AccountDef("252000", "Crédits solidaires (groupes)",      AccountClass.TIERS,      AccountType.ACTIF,   AccountNature.DEBITEUR,  "25"),
    AccountDef("253000", "Crédits habitat",                   AccountClass.TIERS,      AccountType.ACTIF,   AccountNature.DEBITEUR,  "25"),
    AccountDef("254000", "Crédits AGR (activités génératrices de revenus)", AccountClass.TIERS, AccountType.ACTIF, AccountNature.DEBITEUR, "25"),
    AccountDef("257000", "Créances en souffrance",            AccountClass.TIERS,      AccountType.ACTIF,   AccountNature.DEBITEUR,  "25"),
    AccountDef("258000", "Créances irrécouvrables",           AccountClass.TIERS,      AccountType.ACTIF,   AccountNature.DEBITEUR,  "25"),

    # Dépôts membres
    AccountDef("37",     "Dépôts des membres",                AccountClass.TIERS,      AccountType.PASSIF,  AccountNature.CREDITEUR, "4",   is_leaf=False),
    AccountDef("371000", "Dépôts à vue (épargne libre)",      AccountClass.TIERS,      AccountType.PASSIF,  AccountNature.CREDITEUR, "37"),
    AccountDef("371100", "Épargne obligatoire",               AccountClass.TIERS,      AccountType.PASSIF,  AccountNature.CREDITEUR, "37"),
    AccountDef("372000", "Dépôts à terme",                    AccountClass.TIERS,      AccountType.PASSIF,  AccountNature.CREDITEUR, "37"),
    AccountDef("373000", "Plans d'épargne logement",          AccountClass.TIERS,      AccountType.PASSIF,  AccountNature.CREDITEUR, "37"),
    AccountDef("374000", "Épargne-crédit (solidaire)",        AccountClass.TIERS,      AccountType.PASSIF,  AccountNature.CREDITEUR, "37"),

    # Tiers divers
    AccountDef("41",     "Clients / membres débiteurs",       AccountClass.TIERS,      AccountType.ACTIF,   AccountNature.DEBITEUR,  "4",   is_leaf=False),
    AccountDef("411000", "Membres — comptes courants",        AccountClass.TIERS,      AccountType.ACTIF,   AccountNature.DEBITEUR,  "41"),
    AccountDef("412000", "Frais et commissions à recouvrer",  AccountClass.TIERS,      AccountType.ACTIF,   AccountNature.DEBITEUR,  "41"),
    AccountDef("43",     "Personnel",                         AccountClass.TIERS,      AccountType.PASSIF,  AccountNature.CREDITEUR, "4",   is_leaf=False),
    AccountDef("431000", "Rémunérations dues au personnel",   AccountClass.TIERS,      AccountType.PASSIF,  AccountNature.CREDITEUR, "43"),
    AccountDef("44",     "État et organismes sociaux",        AccountClass.TIERS,      AccountType.PASSIF,  AccountNature.CREDITEUR, "4",   is_leaf=False),
    AccountDef("441000", "Impôts et taxes",                   AccountClass.TIERS,      AccountType.PASSIF,  AccountNature.CREDITEUR, "44"),
    AccountDef("442000", "Cotisations sociales",              AccountClass.TIERS,      AccountType.PASSIF,  AccountNature.CREDITEUR, "44"),

    # Classe 5 — Trésorerie
    AccountDef("5",      "TRÉSORERIE",                        AccountClass.TRESORERIE, AccountType.ACTIF,   AccountNature.DEBITEUR,  is_leaf=False),
    AccountDef("57",     "Caisse",                            AccountClass.TRESORERIE, AccountType.ACTIF,   AccountNature.DEBITEUR,  "5",   is_leaf=False),
    AccountDef("571000", "Caisse principale",                 AccountClass.TRESORERIE, AccountType.ACTIF,   AccountNature.DEBITEUR,  "57"),
    AccountDef("571100", "Caisse XOF",                        AccountClass.TRESORERIE, AccountType.ACTIF,   AccountNature.DEBITEUR,  "57"),
    AccountDef("572000", "Caisse secondaire / agence",        AccountClass.TRESORERIE, AccountType.ACTIF,   AccountNature.DEBITEUR,  "57"),
    AccountDef("52",     "Comptes bancaires",                 AccountClass.TRESORERIE, AccountType.ACTIF,   AccountNature.DEBITEUR,  "5",   is_leaf=False),
    AccountDef("521000", "Banque principale",                 AccountClass.TRESORERIE, AccountType.ACTIF,   AccountNature.DEBITEUR,  "52"),
    AccountDef("522000", "Banque secondaire",                 AccountClass.TRESORERIE, AccountType.ACTIF,   AccountNature.DEBITEUR,  "52"),

    # Classe 6 — Charges
    AccountDef("6",      "CHARGES",                           AccountClass.CHARGES,    AccountType.CHARGE,  AccountNature.DEBITEUR,  is_leaf=False),
    AccountDef("61",     "Charges de personnel",              AccountClass.CHARGES,    AccountType.CHARGE,  AccountNature.DEBITEUR,  "6",   is_leaf=False),
    AccountDef("611000", "Salaires et traitements",           AccountClass.CHARGES,    AccountType.CHARGE,  AccountNature.DEBITEUR,  "61"),
    AccountDef("612000", "Charges sociales patronales",       AccountClass.CHARGES,    AccountType.CHARGE,  AccountNature.DEBITEUR,  "61"),
    AccountDef("63",     "Charges générales d'exploitation",  AccountClass.CHARGES,    AccountType.CHARGE,  AccountNature.DEBITEUR,  "6",   is_leaf=False),
    AccountDef("631000", "Loyers et charges locatives",       AccountClass.CHARGES,    AccountType.CHARGE,  AccountNature.DEBITEUR,  "63"),
    AccountDef("632000", "Transports et déplacements",        AccountClass.CHARGES,    AccountType.CHARGE,  AccountNature.DEBITEUR,  "63"),
    AccountDef("633000", "Fournitures de bureau",             AccountClass.CHARGES,    AccountType.CHARGE,  AccountNature.DEBITEUR,  "63"),
    AccountDef("66",     "Charges financières",               AccountClass.CHARGES,    AccountType.CHARGE,  AccountNature.DEBITEUR,  "6",   is_leaf=False),
    AccountDef("663000", "Intérêts sur dépôts membres",       AccountClass.CHARGES,    AccountType.CHARGE,  AccountNature.DEBITEUR,  "66"),
    AccountDef("664000", "Intérêts sur refinancements",       AccountClass.CHARGES,    AccountType.CHARGE,  AccountNature.DEBITEUR,  "66"),
    AccountDef("69",     "Dotations aux provisions",          AccountClass.CHARGES,    AccountType.CHARGE,  AccountNature.DEBITEUR,  "6",   is_leaf=False),
    AccountDef("694000", "Provisions créances en souffrance", AccountClass.CHARGES,    AccountType.CHARGE,  AccountNature.DEBITEUR,  "69"),
    AccountDef("694100", "Provisions créances irrécouvrables",AccountClass.CHARGES,    AccountType.CHARGE,  AccountNature.DEBITEUR,  "69"),

    # Classe 7 — Produits
    AccountDef("7",      "PRODUITS",                          AccountClass.PRODUITS,   AccountType.PRODUIT, AccountNature.CREDITEUR, is_leaf=False),
    AccountDef("70",     "Produits financiers",               AccountClass.PRODUITS,   AccountType.PRODUIT, AccountNature.CREDITEUR, "7",   is_leaf=False),
    AccountDef("701000", "Intérêts sur microcrédits",         AccountClass.PRODUITS,   AccountType.PRODUIT, AccountNature.CREDITEUR, "70"),
    AccountDef("701100", "Intérêts crédits solidaires",       AccountClass.PRODUITS,   AccountType.PRODUIT, AccountNature.CREDITEUR, "70"),
    AccountDef("702000", "Commissions et frais de dossier",   AccountClass.PRODUITS,   AccountType.PRODUIT, AccountNature.CREDITEUR, "70"),
    AccountDef("703000", "Pénalités de retard",               AccountClass.PRODUITS,   AccountType.PRODUIT, AccountNature.CREDITEUR, "70"),
    AccountDef("74",     "Subventions d'exploitation",        AccountClass.PRODUITS,   AccountType.PRODUIT, AccountNature.CREDITEUR, "7",   is_leaf=False),
    AccountDef("740000", "Subventions reçues",                AccountClass.PRODUITS,   AccountType.PRODUIT, AccountNature.CREDITEUR, "74"),
    AccountDef("78",     "Reprises sur provisions",           AccountClass.PRODUITS,   AccountType.PRODUIT, AccountNature.CREDITEUR, "7",   is_leaf=False),
    AccountDef("781000", "Reprises provisions créances",      AccountClass.PRODUITS,   AccountType.PRODUIT, AccountNature.CREDITEUR, "78"),
]


# ─── PCEC — Banque Commerciale ────────────────────────────────────────────────

PCEC_ACCOUNTS: list[AccountDef] = [
    # Classe 1 — Opérations de trésorerie et interbancaires
    AccountDef("1",      "TRÉSORERIE ET INTERBANCAIRE",        AccountClass.CAPITAL,    AccountType.ACTIF,   AccountNature.DEBITEUR,  is_leaf=False),
    AccountDef("11",     "Caisse et assimilés",                AccountClass.CAPITAL,    AccountType.ACTIF,   AccountNature.DEBITEUR,  "1",   is_leaf=False),
    AccountDef("110000", "Caisse XOF",                         AccountClass.CAPITAL,    AccountType.ACTIF,   AccountNature.DEBITEUR,  "11"),
    AccountDef("110100", "Caisse devises",                     AccountClass.CAPITAL,    AccountType.ACTIF,   AccountNature.DEBITEUR,  "11"),
    AccountDef("12",     "Comptes BCEAO",                      AccountClass.CAPITAL,    AccountType.ACTIF,   AccountNature.DEBITEUR,  "1",   is_leaf=False),
    AccountDef("121000", "Compte ordinaire BCEAO",             AccountClass.CAPITAL,    AccountType.ACTIF,   AccountNature.DEBITEUR,  "12"),
    AccountDef("122000", "Réserves obligatoires BCEAO",        AccountClass.CAPITAL,    AccountType.ACTIF,   AccountNature.DEBITEUR,  "12"),
    AccountDef("13",     "Opérations interbancaires actif",    AccountClass.CAPITAL,    AccountType.ACTIF,   AccountNature.DEBITEUR,  "1",   is_leaf=False),
    AccountDef("131000", "Prêts aux confrères",                AccountClass.CAPITAL,    AccountType.ACTIF,   AccountNature.DEBITEUR,  "13"),
    AccountDef("132000", "Comptes nostro (correspondants)",    AccountClass.CAPITAL,    AccountType.ACTIF,   AccountNature.DEBITEUR,  "13"),
    AccountDef("14",     "Opérations interbancaires passif",   AccountClass.CAPITAL,    AccountType.PASSIF,  AccountNature.CREDITEUR, "1",   is_leaf=False),
    AccountDef("141000", "Emprunts auprès des confrères",      AccountClass.CAPITAL,    AccountType.PASSIF,  AccountNature.CREDITEUR, "14"),
    AccountDef("142000", "Comptes vostro (correspondants)",    AccountClass.CAPITAL,    AccountType.PASSIF,  AccountNature.CREDITEUR, "14"),
    AccountDef("15",     "Refinancements BCEAO",               AccountClass.CAPITAL,    AccountType.PASSIF,  AccountNature.CREDITEUR, "1",   is_leaf=False),
    AccountDef("151000", "Pensions livrées BCEAO",             AccountClass.CAPITAL,    AccountType.PASSIF,  AccountNature.CREDITEUR, "15"),

    # Classe 2 — Opérations avec la clientèle
    AccountDef("2",      "OPÉRATIONS CLIENTÈLE",               AccountClass.IMMOBILISE, AccountType.ACTIF,   AccountNature.DEBITEUR,  is_leaf=False),
    AccountDef("21",     "Crédits à court terme",              AccountClass.IMMOBILISE, AccountType.ACTIF,   AccountNature.DEBITEUR,  "2",   is_leaf=False),
    AccountDef("211000", "Facilités de caisse",                AccountClass.IMMOBILISE, AccountType.ACTIF,   AccountNature.DEBITEUR,  "21"),
    AccountDef("212000", "Crédits de campagne",                AccountClass.IMMOBILISE, AccountType.ACTIF,   AccountNature.DEBITEUR,  "21"),
    AccountDef("213000", "Crédits d'escompte",                 AccountClass.IMMOBILISE, AccountType.ACTIF,   AccountNature.DEBITEUR,  "21"),
    AccountDef("22",     "Crédits à moyen terme",              AccountClass.IMMOBILISE, AccountType.ACTIF,   AccountNature.DEBITEUR,  "2",   is_leaf=False),
    AccountDef("221000", "Crédits équipement",                 AccountClass.IMMOBILISE, AccountType.ACTIF,   AccountNature.DEBITEUR,  "22"),
    AccountDef("222000", "Crédits habitat",                    AccountClass.IMMOBILISE, AccountType.ACTIF,   AccountNature.DEBITEUR,  "22"),
    AccountDef("23",     "Crédits à long terme",               AccountClass.IMMOBILISE, AccountType.ACTIF,   AccountNature.DEBITEUR,  "2",   is_leaf=False),
    AccountDef("231000", "Prêts immobiliers",                  AccountClass.IMMOBILISE, AccountType.ACTIF,   AccountNature.DEBITEUR,  "23"),
    AccountDef("24",     "Créances douteuses",                 AccountClass.IMMOBILISE, AccountType.ACTIF,   AccountNature.DEBITEUR,  "2",   is_leaf=False),
    AccountDef("241000", "Créances impayées",                  AccountClass.IMMOBILISE, AccountType.ACTIF,   AccountNature.DEBITEUR,  "24"),
    AccountDef("242000", "Créances contentieuses",             AccountClass.IMMOBILISE, AccountType.ACTIF,   AccountNature.DEBITEUR,  "24"),
    AccountDef("25",     "Dépôts et comptes créditeurs",       AccountClass.IMMOBILISE, AccountType.PASSIF,  AccountNature.CREDITEUR, "2",   is_leaf=False),
    AccountDef("251000", "Comptes courants clients",           AccountClass.IMMOBILISE, AccountType.PASSIF,  AccountNature.CREDITEUR, "25"),
    AccountDef("252000", "Comptes d'épargne",                  AccountClass.IMMOBILISE, AccountType.PASSIF,  AccountNature.CREDITEUR, "25"),
    AccountDef("253000", "Dépôts à terme",                     AccountClass.IMMOBILISE, AccountType.PASSIF,  AccountNature.CREDITEUR, "25"),
    AccountDef("254000", "Bons de caisse",                     AccountClass.IMMOBILISE, AccountType.PASSIF,  AccountNature.CREDITEUR, "25"),

    # Classe 3 — Opérations sur titres
    AccountDef("3",      "OPÉRATIONS SUR TITRES",              AccountClass.STOCK,      AccountType.ACTIF,   AccountNature.DEBITEUR,  is_leaf=False),
    AccountDef("31",     "Titres de transaction",              AccountClass.STOCK,      AccountType.ACTIF,   AccountNature.DEBITEUR,  "3",   is_leaf=False),
    AccountDef("311000", "Bons du Trésor",                     AccountClass.STOCK,      AccountType.ACTIF,   AccountNature.DEBITEUR,  "31"),
    AccountDef("312000", "Obligations",                        AccountClass.STOCK,      AccountType.ACTIF,   AccountNature.DEBITEUR,  "31"),
    AccountDef("32",     "Titres de placement",                AccountClass.STOCK,      AccountType.ACTIF,   AccountNature.DEBITEUR,  "3",   is_leaf=False),
    AccountDef("321000", "Titres BCEAO",                       AccountClass.STOCK,      AccountType.ACTIF,   AccountNature.DEBITEUR,  "32"),
    AccountDef("33",     "Lettres de crédit (LC)",             AccountClass.STOCK,      AccountType.ACTIF,   AccountNature.DEBITEUR,  "3",   is_leaf=False),
    AccountDef("331000", "LC import ouverts",                  AccountClass.STOCK,      AccountType.ACTIF,   AccountNature.DEBITEUR,  "33"),
    AccountDef("332000", "LC export confirmés",                AccountClass.STOCK,      AccountType.ACTIF,   AccountNature.DEBITEUR,  "33"),

    # Classe 4 — Valeurs immobilisées
    AccountDef("4",      "VALEURS IMMOBILISÉES",               AccountClass.TIERS,      AccountType.ACTIF,   AccountNature.DEBITEUR,  is_leaf=False),
    AccountDef("41",     "Immobilisations incorporelles",      AccountClass.TIERS,      AccountType.ACTIF,   AccountNature.DEBITEUR,  "4",   is_leaf=False),
    AccountDef("411000", "Fonds commercial",                   AccountClass.TIERS,      AccountType.ACTIF,   AccountNature.DEBITEUR,  "41"),
    AccountDef("412000", "Logiciels bancaires",                AccountClass.TIERS,      AccountType.ACTIF,   AccountNature.DEBITEUR,  "41"),
    AccountDef("42",     "Immobilisations corporelles",        AccountClass.TIERS,      AccountType.ACTIF,   AccountNature.DEBITEUR,  "4",   is_leaf=False),
    AccountDef("421000", "Terrains et constructions",          AccountClass.TIERS,      AccountType.ACTIF,   AccountNature.DEBITEUR,  "42"),
    AccountDef("422000", "Matériels et équipements",           AccountClass.TIERS,      AccountType.ACTIF,   AccountNature.DEBITEUR,  "42"),
    AccountDef("43",     "Participations et titres détenus",   AccountClass.TIERS,      AccountType.ACTIF,   AccountNature.DEBITEUR,  "4",   is_leaf=False),
    AccountDef("431000", "Participations (filiales)",          AccountClass.TIERS,      AccountType.ACTIF,   AccountNature.DEBITEUR,  "43"),
    AccountDef("44",     "Autres créances",                    AccountClass.TIERS,      AccountType.ACTIF,   AccountNature.DEBITEUR,  "4",   is_leaf=False),
    AccountDef("441000", "Impôts et taxes à récupérer",        AccountClass.TIERS,      AccountType.ACTIF,   AccountNature.DEBITEUR,  "44"),
    AccountDef("45",     "Autres dettes",                      AccountClass.TIERS,      AccountType.PASSIF,  AccountNature.CREDITEUR, "4",   is_leaf=False),
    AccountDef("451000", "Fournisseurs",                       AccountClass.TIERS,      AccountType.PASSIF,  AccountNature.CREDITEUR, "45"),
    AccountDef("452000", "Personnel",                          AccountClass.TIERS,      AccountType.PASSIF,  AccountNature.CREDITEUR, "45"),
    AccountDef("453000", "Impôts et taxes dus",                AccountClass.TIERS,      AccountType.PASSIF,  AccountNature.CREDITEUR, "45"),

    # Classe 5 — Provisions et fonds propres
    AccountDef("5",      "FONDS PROPRES ET PROVISIONS",        AccountClass.TRESORERIE, AccountType.PASSIF,  AccountNature.CREDITEUR, is_leaf=False),
    AccountDef("51",     "Capital et réserves",                AccountClass.TRESORERIE, AccountType.PASSIF,  AccountNature.CREDITEUR, "5",   is_leaf=False),
    AccountDef("511000", "Capital social",                     AccountClass.TRESORERIE, AccountType.PASSIF,  AccountNature.CREDITEUR, "51"),
    AccountDef("512000", "Réserve légale",                     AccountClass.TRESORERIE, AccountType.PASSIF,  AccountNature.CREDITEUR, "51"),
    AccountDef("513000", "Réserves libres",                    AccountClass.TRESORERIE, AccountType.PASSIF,  AccountNature.CREDITEUR, "51"),
    AccountDef("514000", "Report à nouveau",                   AccountClass.TRESORERIE, AccountType.PASSIF,  AccountNature.CREDITEUR, "51"),
    AccountDef("515000", "Résultat de l'exercice",             AccountClass.TRESORERIE, AccountType.PASSIF,  AccountNature.CREDITEUR, "51"),
    AccountDef("52",     "Provisions pour risques",            AccountClass.TRESORERIE, AccountType.PASSIF,  AccountNature.CREDITEUR, "5",   is_leaf=False),
    AccountDef("521000", "Provisions créances douteuses",      AccountClass.TRESORERIE, AccountType.PASSIF,  AccountNature.CREDITEUR, "52"),
    AccountDef("522000", "Provisions risques et charges",      AccountClass.TRESORERIE, AccountType.PASSIF,  AccountNature.CREDITEUR, "52"),
    AccountDef("53",     "Dettes subordonnées",                AccountClass.TRESORERIE, AccountType.PASSIF,  AccountNature.CREDITEUR, "5",   is_leaf=False),
    AccountDef("531000", "Emprunts subordonnés",               AccountClass.TRESORERIE, AccountType.PASSIF,  AccountNature.CREDITEUR, "53"),

    # Classe 6 — Charges
    AccountDef("6",      "CHARGES",                            AccountClass.CHARGES,    AccountType.CHARGE,  AccountNature.DEBITEUR,  is_leaf=False),
    AccountDef("61",     "Charges d'intérêts",                 AccountClass.CHARGES,    AccountType.CHARGE,  AccountNature.DEBITEUR,  "6",   is_leaf=False),
    AccountDef("611000", "Intérêts sur dépôts clientèle",      AccountClass.CHARGES,    AccountType.CHARGE,  AccountNature.DEBITEUR,  "61"),
    AccountDef("612000", "Intérêts sur emprunts interbancaires",AccountClass.CHARGES,   AccountType.CHARGE,  AccountNature.DEBITEUR,  "61"),
    AccountDef("613000", "Intérêts sur refinancements BCEAO",  AccountClass.CHARGES,    AccountType.CHARGE,  AccountNature.DEBITEUR,  "61"),
    AccountDef("62",     "Commissions versées",                AccountClass.CHARGES,    AccountType.CHARGE,  AccountNature.DEBITEUR,  "6",   is_leaf=False),
    AccountDef("621000", "Commissions sur LC",                 AccountClass.CHARGES,    AccountType.CHARGE,  AccountNature.DEBITEUR,  "62"),
    AccountDef("63",     "Charges de personnel",               AccountClass.CHARGES,    AccountType.CHARGE,  AccountNature.DEBITEUR,  "6",   is_leaf=False),
    AccountDef("631000", "Salaires et traitements",            AccountClass.CHARGES,    AccountType.CHARGE,  AccountNature.DEBITEUR,  "63"),
    AccountDef("632000", "Charges sociales",                   AccountClass.CHARGES,    AccountType.CHARGE,  AccountNature.DEBITEUR,  "63"),
    AccountDef("64",     "Charges générales d'exploitation",   AccountClass.CHARGES,    AccountType.CHARGE,  AccountNature.DEBITEUR,  "6",   is_leaf=False),
    AccountDef("641000", "Loyers",                             AccountClass.CHARGES,    AccountType.CHARGE,  AccountNature.DEBITEUR,  "64"),
    AccountDef("642000", "Frais informatiques",                AccountClass.CHARGES,    AccountType.CHARGE,  AccountNature.DEBITEUR,  "64"),
    AccountDef("67",     "Dotations aux amortissements",       AccountClass.CHARGES,    AccountType.CHARGE,  AccountNature.DEBITEUR,  "6",   is_leaf=False),
    AccountDef("671000", "Amortissements immobilisations",     AccountClass.CHARGES,    AccountType.CHARGE,  AccountNature.DEBITEUR,  "67"),
    AccountDef("68",     "Dotations aux provisions",           AccountClass.CHARGES,    AccountType.CHARGE,  AccountNature.DEBITEUR,  "6",   is_leaf=False),
    AccountDef("681000", "Provisions créances douteuses",      AccountClass.CHARGES,    AccountType.CHARGE,  AccountNature.DEBITEUR,  "68"),

    # Classe 7 — Produits
    AccountDef("7",      "PRODUITS",                           AccountClass.PRODUITS,   AccountType.PRODUIT, AccountNature.CREDITEUR, is_leaf=False),
    AccountDef("71",     "Produits d'intérêts",                AccountClass.PRODUITS,   AccountType.PRODUIT, AccountNature.CREDITEUR, "7",   is_leaf=False),
    AccountDef("711000", "Intérêts sur crédits court terme",   AccountClass.PRODUITS,   AccountType.PRODUIT, AccountNature.CREDITEUR, "71"),
    AccountDef("712000", "Intérêts sur crédits moyen terme",   AccountClass.PRODUITS,   AccountType.PRODUIT, AccountNature.CREDITEUR, "71"),
    AccountDef("713000", "Intérêts sur crédits long terme",    AccountClass.PRODUITS,   AccountType.PRODUIT, AccountNature.CREDITEUR, "71"),
    AccountDef("714000", "Intérêts sur placements interbancaires", AccountClass.PRODUITS, AccountType.PRODUIT, AccountNature.CREDITEUR, "71"),
    AccountDef("72",     "Commissions reçues",                 AccountClass.PRODUITS,   AccountType.PRODUIT, AccountNature.CREDITEUR, "7",   is_leaf=False),
    AccountDef("721000", "Commissions sur engagements",        AccountClass.PRODUITS,   AccountType.PRODUIT, AccountNature.CREDITEUR, "72"),
    AccountDef("722000", "Commissions LC et garanties",        AccountClass.PRODUITS,   AccountType.PRODUIT, AccountNature.CREDITEUR, "72"),
    AccountDef("723000", "Frais de tenue de compte",           AccountClass.PRODUITS,   AccountType.PRODUIT, AccountNature.CREDITEUR, "72"),
    AccountDef("73",     "Produits sur titres",                AccountClass.PRODUITS,   AccountType.PRODUIT, AccountNature.CREDITEUR, "7",   is_leaf=False),
    AccountDef("731000", "Dividendes reçus",                   AccountClass.PRODUITS,   AccountType.PRODUIT, AccountNature.CREDITEUR, "73"),
    AccountDef("78",     "Reprises sur provisions",            AccountClass.PRODUITS,   AccountType.PRODUIT, AccountNature.CREDITEUR, "7",   is_leaf=False),
    AccountDef("781000", "Reprises provisions créances",       AccountClass.PRODUITS,   AccountType.PRODUIT, AccountNature.CREDITEUR, "78"),
]


# ─── Journaux par template ────────────────────────────────────────────────────

COMMON_JOURNALS = [
    {"code": "GJ", "name": "Journal Général",    "type": "GJ", "prefix": "GJ"},
    {"code": "OD", "name": "Opérations Diverses","type": "OD", "prefix": "OD"},
    {"code": "AN", "name": "À-Nouveau",           "type": "AN", "prefix": "AN"},
    {"code": "EX", "name": "Extournes",           "type": "EX", "prefix": "EX"},
]

PCIMF_JOURNALS = COMMON_JOURNALS + [
    {"code": "CJ", "name": "Journal de Caisse",  "type": "CJ", "prefix": "CJ"},
    {"code": "BJ", "name": "Journal de Banque",  "type": "BJ", "prefix": "BJ"},
    {"code": "CR", "name": "Journal Crédits",    "type": "CR", "prefix": "CR"},
    {"code": "EP", "name": "Journal Épargne",    "type": "EP", "prefix": "EP"},
]

PCEC_JOURNALS = COMMON_JOURNALS + [
    {"code": "CJ", "name": "Journal de Caisse",            "type": "CJ", "prefix": "CJ"},
    {"code": "BJ", "name": "Journal de Banque",            "type": "BJ", "prefix": "BJ"},
    {"code": "IB", "name": "Journal Interbancaire",        "type": "IB", "prefix": "IB"},
    {"code": "TR", "name": "Journal Titres",               "type": "TR", "prefix": "TR"},
    {"code": "CR", "name": "Journal Crédits",              "type": "CR", "prefix": "CR"},
    {"code": "LC", "name": "Journal Lettres de Crédit",    "type": "LC", "prefix": "LC"},
    {"code": "FX", "name": "Journal Change / Devises",     "type": "FX", "prefix": "FX"},
]


# ─── Registre des templates ───────────────────────────────────────────────────

TEMPLATES: dict[str, PlanTemplate] = {
    "pcimf": PlanTemplate(
        id="pcimf",
        name="PCIMF — Microfinance",
        description=(
            "Plan Comptable des Institutions de MicroFinance (BCEAO/UEMOA). "
            "Adapté aux IMF, coopératives d'épargne-crédit, mutuelles. "
            "Inclut les comptes pour épargne obligatoire, crédits solidaires et groupes villageois."
        ),
        target="MICROFINANCE",
        accounts=PCIMF_ACCOUNTS,
        journal_codes=PCIMF_JOURNALS,
    ),
    "pcec": PlanTemplate(
        id="pcec",
        name="PCEC — Banque Commerciale",
        description=(
            "Plan Comptable des Établissements de Crédit (BCEAO). "
            "Adapté aux banques commerciales agréées. "
            "Inclut les comptes interbancaires, lettres de crédit, opérations sur titres et devises."
        ),
        target="BANK",
        accounts=PCEC_ACCOUNTS,
        journal_codes=PCEC_JOURNALS,
    ),
    "custom": PlanTemplate(
        id="custom",
        name="Plan personnalisé",
        description=(
            "Aucun compte pré-chargé. "
            "L'institution construit entièrement son plan de comptes depuis l'interface."
        ),
        target="CUSTOM",
        accounts=[],
        journal_codes=COMMON_JOURNALS,
    ),
}
