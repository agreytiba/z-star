-- =============================================================================
-- zuristar MySQL Schema
-- Generated from PostgreSQL schema for MySQL compatibility
-- =============================================================================

SET FOREIGN_KEY_CHECKS = 0;

-- =============================================================================
-- Django built-in tables (auth, contenttypes, sessions)
-- =============================================================================

CREATE TABLE IF NOT EXISTS django_migrations (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    app         VARCHAR(255) NOT NULL,
    name        VARCHAR(255) NOT NULL,
    applied     DATETIME(6)  NOT NULL
);

CREATE TABLE IF NOT EXISTS django_content_type (
    id        INT AUTO_INCREMENT PRIMARY KEY,
    app_label VARCHAR(100) NOT NULL,
    model     VARCHAR(100) NOT NULL,
    UNIQUE (app_label, model)
);

CREATE TABLE IF NOT EXISTS auth_permission (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(255)  NOT NULL,
    content_type_id INT           NOT NULL,
    codename        VARCHAR(100)  NOT NULL,
    UNIQUE (content_type_id, codename),
    FOREIGN KEY (content_type_id) REFERENCES django_content_type(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS auth_group (
    id   INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(150) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS auth_group_permissions (
    id            BIGINT AUTO_INCREMENT PRIMARY KEY,
    group_id      INT NOT NULL,
    permission_id INT NOT NULL,
    UNIQUE (group_id, permission_id),
    FOREIGN KEY (group_id) REFERENCES auth_group(id) ON DELETE CASCADE,
    FOREIGN KEY (permission_id) REFERENCES auth_permission(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS django_admin_log (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    action_time     DATETIME(6) NOT NULL,
    object_id       LONGTEXT,
    object_repr     VARCHAR(200) NOT NULL,
    action_flag     SMALLINT UNSIGNED NOT NULL,
    change_message  LONGTEXT NOT NULL,
    content_type_id INT,
    user_id         CHAR(36) NOT NULL,
    FOREIGN KEY (content_type_id) REFERENCES django_content_type(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS django_session (
    session_key  VARCHAR(40) PRIMARY KEY,
    session_data LONGTEXT    NOT NULL,
    expire_date  DATETIME(6) NOT NULL,
    INDEX (expire_date)
);

-- =============================================================================
-- api_user  (custom AbstractUser)
-- =============================================================================

CREATE TABLE IF NOT EXISTS api_user (
    id           CHAR(36)     PRIMARY KEY,
    password     VARCHAR(128) NOT NULL,
    last_login   DATETIME(6),
    is_superuser TINYINT(1)   NOT NULL DEFAULT 0,
    username     VARCHAR(150) NOT NULL UNIQUE,
    first_name   VARCHAR(150) NOT NULL DEFAULT '',
    last_name    VARCHAR(150) NOT NULL DEFAULT '',
    is_staff     TINYINT(1)   NOT NULL DEFAULT 0,
    is_active    TINYINT(1)   NOT NULL DEFAULT 1,
    date_joined  DATETIME(6)  NOT NULL,
    email        VARCHAR(254) NOT NULL UNIQUE
);

CREATE INDEX api_user_email_idx ON api_user (email);

-- M2M: user ↔ group
CREATE TABLE IF NOT EXISTS api_user_groups (
    id       BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id  CHAR(36) NOT NULL,
    group_id INT      NOT NULL,
    UNIQUE (user_id, group_id),
    FOREIGN KEY (user_id) REFERENCES api_user(id) ON DELETE CASCADE,
    FOREIGN KEY (group_id) REFERENCES auth_group(id) ON DELETE CASCADE
);

-- M2M: user ↔ permission
CREATE TABLE IF NOT EXISTS api_user_user_permissions (
    id            BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id       CHAR(36) NOT NULL,
    permission_id INT      NOT NULL,
    UNIQUE (user_id, permission_id),
    FOREIGN KEY (user_id) REFERENCES api_user(id) ON DELETE CASCADE,
    FOREIGN KEY (permission_id) REFERENCES auth_permission(id) ON DELETE CASCADE
);

-- User FK for django_admin_log
ALTER TABLE django_admin_log
    ADD CONSTRAINT django_admin_log_user_id_fk
        FOREIGN KEY (user_id) REFERENCES api_user(id) ON DELETE CASCADE;

-- =============================================================================
-- api_profile
-- =============================================================================

CREATE TABLE IF NOT EXISTS api_profile (
    id                BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id           CHAR(36)     NOT NULL UNIQUE,
    full_name         VARCHAR(255),
    role              VARCHAR(20)  NOT NULL DEFAULT 'customer',
    gender            VARCHAR(10),
    avatar_url        LONGTEXT,
    is_email_verified TINYINT(1)   NOT NULL DEFAULT 0,
    phone_number      VARCHAR(20),
    created_at        DATETIME(6)  NOT NULL,
    updated_at        DATETIME(6)  NOT NULL,
    FOREIGN KEY (user_id) REFERENCES api_user(id) ON DELETE CASCADE
);

-- =============================================================================
-- api_salon
-- =============================================================================

CREATE TABLE IF NOT EXISTS api_salon (
    id                   CHAR(36)     PRIMARY KEY,
    owner_id             BIGINT       NOT NULL,
    name                 VARCHAR(255) NOT NULL,
    description          LONGTEXT,
    address              LONGTEXT,
    latitude             DOUBLE       NOT NULL DEFAULT 0.0,
    longitude            DOUBLE       NOT NULL DEFAULT 0.0,
    phone                VARCHAR(20),
    email                VARCHAR(254),
    website              VARCHAR(200),
    opening_hours        JSON,
    available_time_slots JSON         NOT NULL,
    images               JSON         NOT NULL,
    is_verified          TINYINT(1)   NOT NULL DEFAULT 0,
    is_active            TINYINT(1)   NOT NULL DEFAULT 1,
    is_mobile_service    TINYINT(1)   NOT NULL DEFAULT 0,
    is_in_salon          TINYINT(1)   NOT NULL DEFAULT 1,
    gender_specific      VARCHAR(20)  NOT NULL DEFAULT 'unisex',
    rating               DOUBLE       NOT NULL DEFAULT 0.0,
    review_count         INT          NOT NULL DEFAULT 0,
    tier                 VARCHAR(20)  NOT NULL DEFAULT 'demo',
    subscription_plan    VARCHAR(20)  NOT NULL DEFAULT 'free',
    created_at           DATETIME(6)  NOT NULL,
    updated_at           DATETIME(6)  NOT NULL,
    FOREIGN KEY (owner_id) REFERENCES api_profile(id) ON DELETE CASCADE
);

CREATE INDEX api_salon_owner_id_idx ON api_salon (owner_id);

-- =============================================================================
-- api_salonservice
-- =============================================================================

CREATE TABLE IF NOT EXISTS api_salonservice (
    id               CHAR(36)      PRIMARY KEY,
    salon_id         CHAR(36)      NOT NULL,
    name             VARCHAR(255)  NOT NULL,
    description      LONGTEXT,
    price            DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    duration_minutes INT           NOT NULL DEFAULT 60,
    category         VARCHAR(100),
    subcategory      VARCHAR(100),
    service_group    VARCHAR(100),
    session_count    INT           NOT NULL DEFAULT 1,
    is_available     TINYINT(1)    NOT NULL DEFAULT 1,
    created_at       DATETIME(6)   NOT NULL,
    updated_at       DATETIME(6)   NOT NULL,
    FOREIGN KEY (salon_id) REFERENCES api_salon(id) ON DELETE CASCADE
);

CREATE INDEX api_salonservice_salon_id_idx ON api_salonservice (salon_id);

-- =============================================================================
-- api_salonstaff
-- =============================================================================

CREATE TABLE IF NOT EXISTS api_salonstaff (
    id              CHAR(36)      PRIMARY KEY,
    salon_id        CHAR(36)      NOT NULL,
    profile_id      BIGINT        NOT NULL,
    role            VARCHAR(50)   NOT NULL DEFAULT 'stylist',
    skills          JSON,
    schedule        JSON,
    commission_rate DECIMAL(5,2)  NOT NULL DEFAULT 0.00,
    is_active       TINYINT(1)    NOT NULL DEFAULT 1,
    created_at      DATETIME(6)   NOT NULL,
    updated_at      DATETIME(6)   NOT NULL,
    UNIQUE (salon_id, profile_id),
    FOREIGN KEY (salon_id) REFERENCES api_salon(id) ON DELETE CASCADE,
    FOREIGN KEY (profile_id) REFERENCES api_profile(id) ON DELETE CASCADE
);

CREATE INDEX api_salonstaff_salon_id_idx   ON api_salonstaff (salon_id);
CREATE INDEX api_salonstaff_profile_id_idx ON api_salonstaff (profile_id);

-- =============================================================================
-- api_booking
-- =============================================================================

CREATE TABLE IF NOT EXISTS api_booking (
    id                  CHAR(36)      PRIMARY KEY,
    user_id             CHAR(36)      NOT NULL,
    salon_id            CHAR(36)      NOT NULL,
    staff_id            CHAR(36),
    service_type        VARCHAR(255)  NOT NULL DEFAULT 'Standard Service',
    service_description LONGTEXT,
    booking_date        DATETIME(6)   NOT NULL,
    time_slot           VARCHAR(100)  NOT NULL DEFAULT '10:00 AM',
    price               DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    status              VARCHAR(20)   NOT NULL DEFAULT 'pending',
    is_instant_booking  TINYINT(1)    NOT NULL DEFAULT 0,
    notes               LONGTEXT,
    additional_staff_ids JSON         NOT NULL,
    duration_minutes    INT           NOT NULL DEFAULT 60,
    reminder_set        TINYINT(1)    NOT NULL DEFAULT 0,
    calendar_event_id   VARCHAR(255),
    created_at          DATETIME(6)   NOT NULL,
    updated_at          DATETIME(6)   NOT NULL,
    FOREIGN KEY (user_id) REFERENCES api_user(id) ON DELETE CASCADE,
    FOREIGN KEY (salon_id) REFERENCES api_salon(id) ON DELETE CASCADE,
    FOREIGN KEY (staff_id) REFERENCES api_salonstaff(id) ON DELETE SET NULL
);

CREATE INDEX api_booking_user_id_idx  ON api_booking (user_id);
CREATE INDEX api_booking_salon_id_idx ON api_booking (salon_id);
CREATE INDEX api_booking_status_idx   ON api_booking (status);

-- =============================================================================
-- api_product
-- =============================================================================

CREATE TABLE IF NOT EXISTS api_product (
    id             CHAR(36)      PRIMARY KEY,
    salon_id       CHAR(36)      NOT NULL,
    name           VARCHAR(255)  NOT NULL,
    description    LONGTEXT,
    price          DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    stock_quantity INT           NOT NULL DEFAULT 0,
    category       VARCHAR(100),
    image_url      LONGTEXT,
    is_enabled     TINYINT(1)    NOT NULL DEFAULT 1,
    created_at     DATETIME(6)   NOT NULL,
    updated_at     DATETIME(6)   NOT NULL,
    FOREIGN KEY (salon_id) REFERENCES api_salon(id) ON DELETE CASCADE
);

CREATE INDEX api_product_salon_id_idx ON api_product (salon_id);

-- =============================================================================
-- api_earning
-- =============================================================================

CREATE TABLE IF NOT EXISTS api_earning (
    id          CHAR(36)      PRIMARY KEY,
    owner_id    BIGINT        NOT NULL,
    booking_id  CHAR(36),
    amount      DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    date        DATE          NOT NULL,
    description LONGTEXT,
    created_at  DATETIME(6)   NOT NULL,
    FOREIGN KEY (owner_id) REFERENCES api_profile(id) ON DELETE CASCADE,
    FOREIGN KEY (booking_id) REFERENCES api_booking(id) ON DELETE SET NULL
);

CREATE INDEX api_earning_owner_id_idx ON api_earning (owner_id);

-- =============================================================================
-- api_staffledger
-- =============================================================================

CREATE TABLE IF NOT EXISTS api_staffledger (
    id          CHAR(36)      PRIMARY KEY,
    staff_id    CHAR(36)      NOT NULL,
    owner_id    BIGINT        NOT NULL,
    amount      DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    entry_type  VARCHAR(50)   NOT NULL,
    description LONGTEXT,
    created_at  DATETIME(6)   NOT NULL,
    FOREIGN KEY (staff_id) REFERENCES api_salonstaff(id) ON DELETE CASCADE,
    FOREIGN KEY (owner_id) REFERENCES api_profile(id) ON DELETE CASCADE
);

CREATE INDEX api_staffledger_staff_id_idx ON api_staffledger (staff_id);
CREATE INDEX api_staffledger_owner_id_idx ON api_staffledger (owner_id);

-- =============================================================================
-- api_review
-- =============================================================================

CREATE TABLE IF NOT EXISTS api_review (
    id             CHAR(36)      PRIMARY KEY,
    salon_id       CHAR(36)      NOT NULL,
    booking_id     CHAR(36),
    reviewer_id    CHAR(36)      NOT NULL,
    rating         INT           NOT NULL,
    comment        LONGTEXT,
    owner_response LONGTEXT,
    created_at     DATETIME(6)   NOT NULL,
    FOREIGN KEY (salon_id) REFERENCES api_salon(id) ON DELETE CASCADE,
    FOREIGN KEY (booking_id) REFERENCES api_booking(id) ON DELETE CASCADE,
    FOREIGN KEY (reviewer_id) REFERENCES api_user(id) ON DELETE CASCADE
);

CREATE INDEX api_review_salon_id_idx ON api_review (salon_id);

-- =============================================================================
-- api_salongallery
-- =============================================================================

CREATE TABLE IF NOT EXISTS api_salongallery (
    id             CHAR(36)      PRIMARY KEY,
    salon_id       CHAR(36)      NOT NULL,
    uploaded_by_id BIGINT,
    image_url      LONGTEXT      NOT NULL,
    caption        LONGTEXT,
    is_featured    TINYINT(1)    NOT NULL DEFAULT 0,
    created_at     DATETIME(6)   NOT NULL,
    FOREIGN KEY (salon_id) REFERENCES api_salon(id) ON DELETE CASCADE,
    FOREIGN KEY (uploaded_by_id) REFERENCES api_profile(id) ON DELETE SET NULL
);

CREATE INDEX api_salongallery_salon_id_idx ON api_salongallery (salon_id);

-- =============================================================================
-- api_notification
-- =============================================================================

CREATE TABLE IF NOT EXISTS api_notification (
    id         CHAR(36)      PRIMARY KEY,
    user_id    CHAR(36)      NOT NULL,
    title      VARCHAR(255)  NOT NULL,
    body       LONGTEXT      NOT NULL,
    type       VARCHAR(100)  NOT NULL,
    related_id CHAR(36),
    is_read    TINYINT(1)    NOT NULL DEFAULT 0,
    created_at DATETIME(6)   NOT NULL,
    FOREIGN KEY (user_id) REFERENCES api_user(id) ON DELETE CASCADE
);

CREATE INDEX api_notification_user_id_idx ON api_notification (user_id);

-- =============================================================================
-- api_loyaltypoints
-- =============================================================================

CREATE TABLE IF NOT EXISTS api_loyaltypoints (
    id         BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id    CHAR(36)      NOT NULL UNIQUE,
    points     INT           NOT NULL DEFAULT 0,
    tier       VARCHAR(20)   NOT NULL DEFAULT 'bronze',
    created_at DATETIME(6)   NOT NULL,
    updated_at DATETIME(6)   NOT NULL,
    FOREIGN KEY (user_id) REFERENCES api_user(id) ON DELETE CASCADE
);

-- =============================================================================
-- api_loyaltytransaction
-- =============================================================================

CREATE TABLE IF NOT EXISTS api_loyaltytransaction (
    id               BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id          CHAR(36)      NOT NULL,
    amount           INT           NOT NULL,
    description      LONGTEXT      NOT NULL,
    transaction_type VARCHAR(50)   NOT NULL,
    created_at       DATETIME(6)   NOT NULL,
    FOREIGN KEY (user_id) REFERENCES api_user(id) ON DELETE CASCADE
);

CREATE INDEX api_loyaltytransaction_user_id_idx ON api_loyaltytransaction (user_id);

-- =============================================================================
-- api_fcmtoken
-- =============================================================================

CREATE TABLE IF NOT EXISTS api_fcmtoken (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id     CHAR(36)     NOT NULL,
    token       VARCHAR(255) NOT NULL UNIQUE,
    device_type VARCHAR(50)  NOT NULL,
    created_at  DATETIME(6)  NOT NULL,
    UNIQUE (user_id, token),
    FOREIGN KEY (user_id) REFERENCES api_user(id) ON DELETE CASCADE
);

CREATE INDEX api_fcmtoken_user_id_idx ON api_fcmtoken (user_id);

-- =============================================================================
-- api_otp
-- =============================================================================

CREATE TABLE IF NOT EXISTS api_otp (
    id           BIGINT AUTO_INCREMENT PRIMARY KEY,
    phone_number VARCHAR(20),
    otp_code     VARCHAR(6),
    pin_id       VARCHAR(100),
    email        VARCHAR(254),
    created_at   DATETIME(6)  NOT NULL,
    is_verified  TINYINT(1)   NOT NULL DEFAULT 0
);

-- =============================================================================
-- Mark migrations as applied
-- =============================================================================

INSERT INTO django_migrations (app, name, applied) VALUES
    ('contenttypes', '0001_initial',                            NOW(6)),
    ('contenttypes', '0002_remove_content_type_name',           NOW(6)),
    ('auth',         '0001_initial',                            NOW(6)),
    ('auth',         '0002_alter_permission_name_max_length',    NOW(6)),
    ('auth',         '0003_alter_user_email_max_length',         NOW(6)),
    ('auth',         '0004_alter_user_username_opts',            NOW(6)),
    ('auth',         '0005_alter_user_last_login_null',          NOW(6)),
    ('auth',         '0006_require_contenttypes_0002',           NOW(6)),
    ('auth',         '0007_alter_validators_add_error_messages', NOW(6)),
    ('auth',         '0008_alter_user_username_max_length',      NOW(6)),
    ('auth',         '0009_alter_user_last_name_max_length',     NOW(6)),
    ('auth',         '0010_alter_group_name_max_length',         NOW(6)),
    ('auth',         '0011_update_proxy_permissions',            NOW(6)),
    ('auth',         '0012_alter_user_first_name_max_length',    NOW(6)),
    ('api',          '0001_initial',                            NOW(6)),
    ('api',          '0002_remove_fcmtoken_user_and_more',       NOW(6)),
    ('api',          '0003_remove_booking_end_time_and_more',    NOW(6)),
    ('api',          '0004_fcmtoken',                           NOW(6)),
    ('api',          '0005_salonservice_session_count',          NOW(6)),
    ('api',          '0006_salonservice_subcategory',            NOW(6)),
    ('api',          '0007_otp',                                NOW(6)),
    ('api',          '0008_otp_pin_id_alter_otp_otp_code',       NOW(6)),
    ('api',          '0009_otp_email_alter_otp_phone_number',    NOW(6)),
    ('api',          '0010_profile_gender',                     NOW(6)),
    ('admin',        '0001_initial',                            NOW(6)),
    ('admin',        '0002_logentry_remove_auto_add',            NOW(6)),
    ('admin',        '0003_logentry_add_action_flag_choices',    NOW(6)),
    ('sessions',     '0001_initial',                            NOW(6));


SET FOREIGN_KEY_CHECKS = 1;
