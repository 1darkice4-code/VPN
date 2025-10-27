-- Скрипт инициализации базы данных VPN Bot

-- Таблица пользователей
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    username VARCHAR(255),
    first_name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблица подписок
CREATE TABLE IF NOT EXISTS subscriptions (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(telegram_id),
    plan TEXT,
    client_ip TEXT,
    config TEXT,
    config_key INTEGER DEFAULT 0,
    start_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    end_date TIMESTAMP,
    active BOOLEAN DEFAULT TRUE
);

-- Таблица VPN профилей
CREATE TABLE IF NOT EXISTS vpn_profiles (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(telegram_id),
    vpn_type VARCHAR(50),
    config TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблица для хранения public_key конфигураций WireGuard
CREATE TABLE IF NOT EXISTS configs (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(telegram_id),
    config_key INTEGER NOT NULL,
    public_key TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, config_key)
);

-- Индексы для ускорения запросов
CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_vpn_profiles_user_id ON vpn_profiles(user_id);
CREATE INDEX IF NOT EXISTS idx_configs_public_key ON configs(public_key);
CREATE INDEX IF NOT EXISTS idx_configs_user_config_key ON configs(user_id, config_key);

-- Комментарии к таблицам
COMMENT ON TABLE users IS 'Пользователи Telegram бота';
COMMENT ON TABLE subscriptions IS 'Подписки пользователей';
COMMENT ON TABLE vpn_profiles IS 'VPN профили пользователей';
COMMENT ON TABLE configs IS 'Public ключи WireGuard конфигураций для проверки активности';

