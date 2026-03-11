-- NOTAIRE APP — Initialisation base de données

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Utilisateurs et auth
CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email           VARCHAR(255) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    role            VARCHAR(20) DEFAULT 'client' CHECK (role IN ('admin','notaire','clerc','client')),
    is_active       BOOLEAN DEFAULT true,
    is_verified     BOOLEAN DEFAULT false,
    totp_secret     VARCHAR(100),
    totp_enabled    BOOLEAN DEFAULT false,
    failed_login_count INTEGER DEFAULT 0,
    locked_until    TIMESTAMP,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS refresh_tokens (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID REFERENCES users(id) ON DELETE CASCADE,
    token_hash  VARCHAR(255) UNIQUE NOT NULL,
    expires_at  TIMESTAMP NOT NULL,
    revoked     BOOLEAN DEFAULT false,
    ip_address  VARCHAR(45),
    user_agent  TEXT,
    created_at  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID REFERENCES users(id),
    action          VARCHAR(100) NOT NULL,
    resource_type   VARCHAR(50),
    resource_id     UUID,
    ip_address      VARCHAR(45),
    details         JSONB DEFAULT '{}',
    created_at      TIMESTAMP DEFAULT NOW()
);

-- Clients notaires
CREATE TABLE IF NOT EXISTS clients (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    nom         VARCHAR(100) NOT NULL,
    prenom      VARCHAR(100),
    email       VARCHAR(255) UNIQUE,
    telephone   VARCHAR(20),
    adresse     TEXT,
    created_at  TIMESTAMP DEFAULT NOW(),
    updated_at  TIMESTAMP DEFAULT NOW()
);

-- Dossiers notariaux
CREATE TABLE IF NOT EXISTS dossiers (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    reference       VARCHAR(50) UNIQUE NOT NULL,
    type_acte       VARCHAR(100) NOT NULL,
    statut          VARCHAR(50) DEFAULT 'en_cours',
    client_id       UUID REFERENCES clients(id),
    notaire_id      UUID REFERENCES users(id),
    description     TEXT,
    montant         BIGINT,
    date_signature  DATE,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dossiers_client   ON dossiers(client_id);
CREATE INDEX IF NOT EXISTS idx_dossiers_notaire  ON dossiers(notaire_id);
CREATE INDEX IF NOT EXISTS idx_dossiers_statut   ON dossiers(statut);

-- Documents (data room)
CREATE TABLE IF NOT EXISTS documents (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    dossier_id  UUID REFERENCES dossiers(id) ON DELETE CASCADE,
    nom         VARCHAR(255) NOT NULL,
    type_doc    VARCHAR(100),
    chemin      TEXT NOT NULL,
    taille_bytes INTEGER,
    mime_type   VARCHAR(100),
    uploaded_by UUID REFERENCES users(id),
    created_at  TIMESTAMP DEFAULT NOW()
);

-- Transactions immobilières (données DVF)
CREATE TABLE IF NOT EXISTS transactions (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    date_vente  DATE NOT NULL,
    prix_vente  INTEGER NOT NULL,
    prix_m2     INTEGER,
    surface_m2  NUMERIC(8,2),
    type_bien   VARCHAR(50) NOT NULL,
    nb_pieces   INTEGER,
    surface_terrain_m2 NUMERIC(10,2),
    code_postal VARCHAR(10),
    commune     VARCHAR(100),
    departement VARCHAR(3),
    longitude   NUMERIC(10,7),
    latitude    NUMERIC(10,7),
    nature_mutation VARCHAR(50),
    created_at  TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_transactions_dept   ON transactions(departement);
CREATE INDEX IF NOT EXISTS idx_transactions_cp     ON transactions(code_postal);
CREATE INDEX IF NOT EXISTS idx_transactions_date   ON transactions(date_vente);
CREATE INDEX IF NOT EXISTS idx_transactions_coords ON transactions(latitude, longitude);

-- Successions
CREATE TABLE IF NOT EXISTS successions (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    dossier_id          UUID REFERENCES dossiers(id),
    defunt_nom          VARCHAR(100),
    defunt_prenom       VARCHAR(100),
    defunt_naissance    DATE,
    defunt_deces        DATE,
    regime_matrimonial  VARCHAR(50),
    nb_enfants          INTEGER DEFAULT 0,
    statut_traitement   VARCHAR(50) DEFAULT 'en_cours',
    created_at          TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS heritiers (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    succession_id   UUID REFERENCES successions(id) ON DELETE CASCADE,
    nom             VARCHAR(100) NOT NULL,
    prenom          VARCHAR(100),
    lien_parente    VARCHAR(50) CHECK (lien_parente IN ('conjoint','enfant','petit_enfant','parent','frere_soeur','autre')),
    part_theorique  DECIMAL(5,4),
    adresse         TEXT
);

CREATE TABLE IF NOT EXISTS actifs_successoraux (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    succession_id   UUID REFERENCES successions(id) ON DELETE CASCADE,
    type_actif      VARCHAR(50) CHECK (type_actif IN ('immobilier','compte_bancaire','assurance_vie','vehicule','mobilier','autre')),
    description     TEXT,
    valeur_estimee  BIGINT,
    etablissement   VARCHAR(100),
    reference       VARCHAR(100),
    date_evaluation DATE
);

CREATE TABLE IF NOT EXISTS passifs_successoraux (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    succession_id   UUID REFERENCES successions(id) ON DELETE CASCADE,
    type_passif     VARCHAR(100),
    montant         BIGINT,
    creancier       VARCHAR(100)
);

-- RAG — Chunks de connaissance juridique
CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source      VARCHAR(255) NOT NULL,
    source_type VARCHAR(50) CHECK (source_type IN ('acte_type','jurisprudence','loi','bofip','autre')),
    content     TEXT NOT NULL,
    content_hash VARCHAR(64) UNIQUE,
    embedding   vector(768),
    metadata    JSONB DEFAULT '{}',
    created_at  TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chunks_source    ON knowledge_chunks(source);
CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON knowledge_chunks
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Veille et alertes
CREATE TABLE IF NOT EXISTS veille_rules (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    type        VARCHAR(50) CHECK (type IN ('loi','jurisprudence','fiscalite','immobilier','bodacc')),
    mots_cles   TEXT[],
    code_postal VARCHAR(10),
    dossier_id  UUID REFERENCES dossiers(id),
    actif       BOOLEAN DEFAULT true,
    created_at  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS alertes (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    veille_rule_id  UUID REFERENCES veille_rules(id),
    dossier_id      UUID REFERENCES dossiers(id),
    titre           VARCHAR(255) NOT NULL,
    contenu         TEXT,
    source_url      TEXT,
    impact_estime   VARCHAR(20) CHECK (impact_estime IN ('faible','moyen','fort','critique')),
    lue             BOOLEAN DEFAULT false,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- Signatures électroniques
CREATE TABLE IF NOT EXISTS signatures (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    dossier_id      UUID REFERENCES dossiers(id),
    document_id     UUID REFERENCES documents(id),
    provider        VARCHAR(50),
    external_id     VARCHAR(255),
    statut          VARCHAR(50) DEFAULT 'en_attente',
    signataires     JSONB DEFAULT '[]',
    created_at      TIMESTAMP DEFAULT NOW(),
    completed_at    TIMESTAMP
);

-- Log interactions IA
CREATE TABLE IF NOT EXISTS ai_interactions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    provider        VARCHAR(50),
    model           VARCHAR(100),
    use_case        VARCHAR(100),
    input_tokens    INTEGER DEFAULT 0,
    output_tokens   INTEGER DEFAULT 0,
    duration_ms     INTEGER,
    dossier_id      UUID REFERENCES dossiers(id),
    created_at      TIMESTAMP DEFAULT NOW()
);

-- Pipeline runs (suivi imports DVF)
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source          VARCHAR(50),
    departement     VARCHAR(5),
    statut          VARCHAR(20) DEFAULT 'en_cours',
    nb_lignes       INTEGER DEFAULT 0,
    erreur          TEXT,
    started_at      TIMESTAMP DEFAULT NOW(),
    finished_at     TIMESTAMP
);

-- Vue utile : stats estimation par zone
CREATE OR REPLACE VIEW estimation_stats AS
SELECT
    code_postal,
    commune,
    type_bien,
    COUNT(*) as nb_transactions,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY prix_m2) AS prix_m2_median,
    AVG(prix_m2) AS prix_m2_moyen,
    MIN(prix_m2) AS prix_m2_min,
    MAX(prix_m2) AS prix_m2_max,
    MAX(date_vente) AS derniere_transaction
FROM transactions
WHERE date_vente >= NOW() - INTERVAL '24 months'
GROUP BY code_postal, commune, type_bien;
