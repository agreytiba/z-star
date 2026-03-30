-- =============================================================================
-- zuristar PostgreSQL Schema
-- Generated from Django migrations (0001 → 0010)
-- Run this against a fresh PostgreSQL database before starting the Django server.
-- After running this file, also run: python manage.py migrate --fake-initial
-- to mark all migrations as applied without re-running them.
-- =============================================================================

-- Enable UUID extension (required for UUID primary keys)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================================
-- Django built-in tables (auth, contenttypes, sessions)
-- =============================================================================

CREATE TABLE IF NOT EXISTS django_migrations (
    id          BIGSERIAL PRIMARY KEY,
    app         VARCHAR(255) NOT NULL,
    name        VARCHAR(255) NOT NULL,
    applied     TIMESTAMPTZ  NOT NULL
);

CREATE TABLE IF NOT EXISTS django_content_type (
    id        SERIAL PRIMARY KEY,
    app_label VARCHAR(100) NOT NULL,
    model     VARCHAR(100) NOT NULL,
    CONSTRAINT django_content_type_app_label_model_uniq UNIQUE (app_label, model)
);

CREATE TABLE IF NOT EXISTS auth_permission (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(255)  NOT NULL,
    content_type_id INTEGER       NOT NULL REFERENCES django_content_type(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
    codename        VARCHAR(100)  NOT NULL,
    CONSTRAINT auth_permission_content_type_id_codename_uniq UNIQUE (content_type_id, codename)
);

CREATE TABLE IF NOT EXISTS auth_group (
    id   SERIAL PRIMARY KEY,
    name VARCHAR(150) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS auth_group_permissions (
    id            BIGSERIAL PRIMARY KEY,
    group_id      INTEGER NOT NULL REFERENCES auth_group(id)      ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
    permission_id INTEGER NOT NULL REFERENCES auth_permission(id)  ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT auth_group_permissions_group_id_permission_id_uniq UNIQUE (group_id, permission_id)
);

CREATE TABLE IF NOT EXISTS django_admin_log (
    id              SERIAL      PRIMARY KEY,
    action_time     TIMESTAMPTZ NOT NULL,
    object_id       TEXT,
    object_repr     VARCHAR(200) NOT NULL,
    action_flag     SMALLINT     NOT NULL CHECK (action_flag >= 0),
    change_message  TEXT         NOT NULL,
    content_type_id INTEGER      REFERENCES django_content_type(id) ON DELETE SET NULL DEFERRABLE INITIALLY DEFERRED,
    user_id         UUID         NOT NULL  -- FK to api_user added after that table is created
);

CREATE TABLE IF NOT EXISTS django_session (
    session_key  VARCHAR(40) PRIMARY KEY,
    session_data TEXT        NOT NULL,
    expire_date  TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS django_session_expire_date_idx ON django_session (expire_date);

-- =============================================================================
-- api_user  (custom AbstractUser — migration 0001)
-- =============================================================================

CREATE TABLE IF NOT EXISTS api_user (
    -- AbstractUser fields
    id           UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    password     VARCHAR(128) NOT NULL,
    last_login   TIMESTAMPTZ,
    is_superuser BOOLEAN      NOT NULL DEFAULT FALSE,
    username     VARCHAR(150) NOT NULL UNIQUE,
    first_name   VARCHAR(150) NOT NULL DEFAULT '',
    last_name    VARCHAR(150) NOT NULL DEFAULT '',
    is_staff     BOOLEAN      NOT NULL DEFAULT FALSE,
    is_active    BOOLEAN      NOT NULL DEFAULT TRUE,
    date_joined  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    -- Custom fields
    email        VARCHAR(254) NOT NULL UNIQUE
);

CREATE INDEX IF NOT EXISTS api_user_email_idx ON api_user (email);

-- M2M: user ↔ group
CREATE TABLE IF NOT EXISTS api_user_groups (
    id       BIGSERIAL PRIMARY KEY,
    user_id  UUID    NOT NULL REFERENCES api_user(id)  ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
    group_id INTEGER NOT NULL REFERENCES auth_group(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT api_user_groups_user_id_group_id_uniq UNIQUE (user_id, group_id)
);

-- M2M: user ↔ permission
CREATE TABLE IF NOT EXISTS api_user_user_permissions (
    id            BIGSERIAL PRIMARY KEY,
    user_id       UUID    NOT NULL REFERENCES api_user(id)       ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
    permission_id INTEGER NOT NULL REFERENCES auth_permission(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT api_user_user_permissions_user_id_permission_id_uniq UNIQUE (user_id, permission_id)
);

-- Now that api_user exists, add the FK to django_admin_log
ALTER TABLE django_admin_log
    ADD CONSTRAINT IF NOT EXISTS django_admin_log_user_id_fk
        FOREIGN KEY (user_id) REFERENCES api_user(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED;

-- =============================================================================
-- api_profile  (migration 0001 + 0010 adds gender)
-- =============================================================================

CREATE TABLE IF NOT EXISTS api_profile (
    id                BIGSERIAL    PRIMARY KEY,
    user_id           UUID         NOT NULL UNIQUE REFERENCES api_user(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
    full_name         VARCHAR(255),
    role              VARCHAR(20)  NOT NULL DEFAULT 'customer'
                          CHECK (role IN ('customer', 'salon_owner', 'staff')),
    gender            VARCHAR(10)
                          CHECK (gender IN ('male', 'female', 'other')),   -- added in 0010
    avatar_url        TEXT,
    is_email_verified BOOLEAN      NOT NULL DEFAULT FALSE,
    phone_number      VARCHAR(20),
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- =============================================================================
-- api_salon  (migration 0001, heavily altered in 0003)
-- =============================================================================

CREATE TABLE IF NOT EXISTS api_salon (
    id                   UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    owner_id             BIGINT      NOT NULL REFERENCES api_profile(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
    name                 VARCHAR(255) NOT NULL,
    description          TEXT,
    address              TEXT,
    latitude             DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    longitude            DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    phone                VARCHAR(20),
    email                VARCHAR(254),
    website              VARCHAR(200),
    opening_hours        JSONB,
    available_time_slots JSONB        NOT NULL DEFAULT '[]',
    images               JSONB        NOT NULL DEFAULT '[]',
    is_verified          BOOLEAN      NOT NULL DEFAULT FALSE,
    is_active            BOOLEAN      NOT NULL DEFAULT TRUE,
    is_mobile_service    BOOLEAN      NOT NULL DEFAULT FALSE,
    is_in_salon          BOOLEAN      NOT NULL DEFAULT TRUE,
    gender_specific      VARCHAR(20)  NOT NULL DEFAULT 'unisex',
    rating               DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    review_count         INTEGER      NOT NULL DEFAULT 0,
    tier                 VARCHAR(20)  NOT NULL DEFAULT 'demo',
    subscription_plan    VARCHAR(20)  NOT NULL DEFAULT 'free',
    created_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS api_salon_owner_id_idx ON api_salon (owner_id);

-- =============================================================================
-- api_salonservice  (0001 + 0005 session_count + 0006 subcategory)
-- =============================================================================

CREATE TABLE IF NOT EXISTS api_salonservice (
    id               UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    salon_id         UUID         NOT NULL REFERENCES api_salon(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
    name             VARCHAR(255) NOT NULL,
    description      TEXT,
    price            NUMERIC(10,2) NOT NULL DEFAULT 0.00,
    duration_minutes INTEGER      NOT NULL DEFAULT 60,
    category         VARCHAR(100),
    subcategory      VARCHAR(100),                    -- added in 0006
    service_group    VARCHAR(100),
    session_count    INTEGER      NOT NULL DEFAULT 1, -- added in 0005
    is_available     BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS api_salonservice_salon_id_idx ON api_salonservice (salon_id);

-- =============================================================================
-- api_salonstaff  (migration 0001 + 0003 adds schedule)
-- =============================================================================

CREATE TABLE IF NOT EXISTS api_salonstaff (
    id              UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    salon_id        UUID         NOT NULL REFERENCES api_salon(id)    ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
    profile_id      BIGINT       NOT NULL REFERENCES api_profile(id)  ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
    role            VARCHAR(50)  NOT NULL DEFAULT 'stylist',
    skills          JSONB,
    schedule        JSONB,                            -- added in 0003
    commission_rate NUMERIC(5,2) NOT NULL DEFAULT 0.00,
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT api_salonstaff_salon_profile_uniq UNIQUE (salon_id, profile_id)
);

CREATE INDEX IF NOT EXISTS api_salonstaff_salon_id_idx   ON api_salonstaff (salon_id);
CREATE INDEX IF NOT EXISTS api_salonstaff_profile_id_idx ON api_salonstaff (profile_id);

-- =============================================================================
-- api_booking  (0001 + major reshape in 0002 & 0003)
-- =============================================================================

CREATE TABLE IF NOT EXISTS api_booking (
    id                  UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id             UUID         NOT NULL REFERENCES api_user(id)    ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
    salon_id            UUID         NOT NULL REFERENCES api_salon(id)   ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
    staff_id            UUID         REFERENCES api_salonstaff(id)       ON DELETE SET NULL DEFERRABLE INITIALLY DEFERRED,
    service_type        VARCHAR(255) NOT NULL DEFAULT 'Standard Service',
    service_description TEXT,
    booking_date        TIMESTAMPTZ  NOT NULL,
    time_slot           VARCHAR(100) NOT NULL DEFAULT '10:00 AM',
    price               NUMERIC(10,2) NOT NULL DEFAULT 0.00,
    status              VARCHAR(20)  NOT NULL DEFAULT 'pending'
                            CHECK (status IN ('pending','confirmed','completed','cancelled','rescheduled')),
    is_instant_booking  BOOLEAN      NOT NULL DEFAULT FALSE,
    notes               TEXT,
    additional_staff_ids JSONB       NOT NULL DEFAULT '[]',
    duration_minutes    INTEGER      NOT NULL DEFAULT 60,
    reminder_set        BOOLEAN      NOT NULL DEFAULT FALSE,
    calendar_event_id   VARCHAR(255),
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS api_booking_user_id_idx  ON api_booking (user_id);
CREATE INDEX IF NOT EXISTS api_booking_salon_id_idx ON api_booking (salon_id);
CREATE INDEX IF NOT EXISTS api_booking_status_idx   ON api_booking (status);

-- =============================================================================
-- api_product  (migration 0002 + 0003 adds is_enabled)
-- =============================================================================

CREATE TABLE IF NOT EXISTS api_product (
    id             UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    salon_id       UUID         NOT NULL REFERENCES api_salon(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
    name           VARCHAR(255) NOT NULL,
    description    TEXT,
    price          NUMERIC(10,2) NOT NULL DEFAULT 0.00,
    stock_quantity INTEGER      NOT NULL DEFAULT 0,
    category       VARCHAR(100),
    image_url      TEXT,
    is_enabled     BOOLEAN      NOT NULL DEFAULT TRUE,  -- added in 0003
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS api_product_salon_id_idx ON api_product (salon_id);

-- =============================================================================
-- api_earning  (migration 0002)
-- =============================================================================

CREATE TABLE IF NOT EXISTS api_earning (
    id          UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    owner_id    BIGINT       NOT NULL REFERENCES api_profile(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
    booking_id  UUID         REFERENCES api_booking(id) ON DELETE SET NULL DEFERRABLE INITIALLY DEFERRED,
    amount      NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    date        DATE         NOT NULL,
    description TEXT,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS api_earning_owner_id_idx ON api_earning (owner_id);

-- =============================================================================
-- api_staffledger  (migration 0002)
-- =============================================================================

CREATE TABLE IF NOT EXISTS api_staffledger (
    id          UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    staff_id    UUID         NOT NULL REFERENCES api_salonstaff(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
    owner_id    BIGINT       NOT NULL REFERENCES api_profile(id)    ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
    amount      NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    entry_type  VARCHAR(50)  NOT NULL,
    description TEXT,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS api_staffledger_staff_id_idx ON api_staffledger (staff_id);
CREATE INDEX IF NOT EXISTS api_staffledger_owner_id_idx ON api_staffledger (owner_id);

-- =============================================================================
-- api_review  (migration 0001, altered in 0002 & 0003)
-- =============================================================================

CREATE TABLE IF NOT EXISTS api_review (
    id             UUID    PRIMARY KEY DEFAULT uuid_generate_v4(),
    salon_id       UUID    NOT NULL REFERENCES api_salon(id)   ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
    booking_id     UUID    REFERENCES api_booking(id)          ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
    reviewer_id    UUID    NOT NULL REFERENCES api_user(id)    ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
    rating         INTEGER NOT NULL,
    comment        TEXT,
    owner_response TEXT,                                       -- added in 0002
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS api_review_salon_id_idx ON api_review (salon_id);

-- =============================================================================
-- api_salonservice (already created above)
-- api_salongallery  (migration 0001)
-- =============================================================================

CREATE TABLE IF NOT EXISTS api_salongallery (
    id           UUID    PRIMARY KEY DEFAULT uuid_generate_v4(),
    salon_id     UUID    NOT NULL REFERENCES api_salon(id)    ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
    uploaded_by_id BIGINT REFERENCES api_profile(id)          ON DELETE SET NULL DEFERRABLE INITIALLY DEFERRED,
    image_url    TEXT    NOT NULL,
    caption      TEXT,
    is_featured  BOOLEAN NOT NULL DEFAULT FALSE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS api_salongallery_salon_id_idx ON api_salongallery (salon_id);

-- =============================================================================
-- api_notification  (migration 0001, altered in 0002 — removed data, added related_id)
-- =============================================================================

CREATE TABLE IF NOT EXISTS api_notification (
    id         UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id    UUID         NOT NULL REFERENCES api_user(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
    title      VARCHAR(255) NOT NULL,
    body       TEXT         NOT NULL,
    type       VARCHAR(100) NOT NULL,
    related_id UUID,                                        -- added in 0002
    is_read    BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS api_notification_user_id_idx ON api_notification (user_id);

-- =============================================================================
-- api_loyaltypoints  (migration 0003)
-- =============================================================================

CREATE TABLE IF NOT EXISTS api_loyaltypoints (
    id         BIGSERIAL   PRIMARY KEY,
    user_id    UUID        NOT NULL UNIQUE REFERENCES api_user(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
    points     INTEGER     NOT NULL DEFAULT 0,
    tier       VARCHAR(20) NOT NULL DEFAULT 'bronze',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================================
-- api_loyaltytransaction  (migration 0003)
-- =============================================================================

CREATE TABLE IF NOT EXISTS api_loyaltytransaction (
    id               BIGSERIAL   PRIMARY KEY,
    user_id          UUID        NOT NULL REFERENCES api_user(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
    amount           INTEGER     NOT NULL,
    description      TEXT        NOT NULL,
    transaction_type VARCHAR(50) NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS api_loyaltytransaction_user_id_idx ON api_loyaltytransaction (user_id);

-- =============================================================================
-- api_fcmtoken  (migration 0004 — replaces the 0001 version that was deleted in 0002)
-- =============================================================================

CREATE TABLE IF NOT EXISTS api_fcmtoken (
    id          BIGSERIAL    PRIMARY KEY,
    user_id     UUID         NOT NULL REFERENCES api_user(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
    token       VARCHAR(255) NOT NULL UNIQUE,
    device_type VARCHAR(50)  NOT NULL,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT api_fcmtoken_user_id_token_uniq UNIQUE (user_id, token)
);

CREATE INDEX IF NOT EXISTS api_fcmtoken_user_id_idx ON api_fcmtoken (user_id);

-- =============================================================================
-- api_otp  (migration 0007 + 0008 pin_id + 0009 email)
-- =============================================================================

CREATE TABLE IF NOT EXISTS api_otp (
    id           BIGSERIAL    PRIMARY KEY,
    phone_number VARCHAR(20),                           -- made nullable in 0009
    otp_code     VARCHAR(6),                            -- made nullable in 0008
    pin_id       VARCHAR(100),                          -- added in 0008
    email        VARCHAR(254),                          -- added in 0009
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    is_verified  BOOLEAN      NOT NULL DEFAULT FALSE
);

-- =============================================================================
-- Mark all migrations as applied in django_migrations table
-- (use this when running --fake-initial, or insert manually after schema creation)
-- =============================================================================

INSERT INTO django_migrations (app, name, applied) VALUES
    ('contenttypes', '0001_initial',                            NOW()),
    ('contenttypes', '0002_remove_content_type_name',           NOW()),
    ('auth',         '0001_initial',                            NOW()),
    ('auth',         '0002_alter_permission_name_max_length',    NOW()),
    ('auth',         '0003_alter_user_email_max_length',         NOW()),
    ('auth',         '0004_alter_user_username_opts',            NOW()),
    ('auth',         '0005_alter_user_last_login_null',          NOW()),
    ('auth',         '0006_require_contenttypes_0002',           NOW()),
    ('auth',         '0007_alter_validators_add_error_messages', NOW()),
    ('auth',         '0008_alter_user_username_max_length',      NOW()),
    ('auth',         '0009_alter_user_last_name_max_length',     NOW()),
    ('auth',         '0010_alter_group_name_max_length',         NOW()),
    ('auth',         '0011_update_proxy_permissions',            NOW()),
    ('auth',         '0012_alter_user_first_name_max_length',    NOW()),
    ('api',          '0001_initial',                            NOW()),
    ('api',          '0002_remove_fcmtoken_user_and_more',       NOW()),
    ('api',          '0003_remove_booking_end_time_and_more',    NOW()),
    ('api',          '0004_fcmtoken',                           NOW()),
    ('api',          '0005_salonservice_session_count',          NOW()),
    ('api',          '0006_salonservice_subcategory',            NOW()),
    ('api',          '0007_otp',                                NOW()),
    ('api',          '0008_otp_pin_id_alter_otp_otp_code',       NOW()),
    ('api',          '0009_otp_email_alter_otp_phone_number',    NOW()),
    ('api',          '0010_profile_gender',                     NOW()),
    ('admin',        '0001_initial',                            NOW()),
    ('admin',        '0002_logentry_remove_auto_add',            NOW()),
    ('admin',        '0003_logentry_add_action_flag_choices',    NOW()),
    ('sessions',     '0001_initial',                            NOW())
ON CONFLICT DO NOTHING;
