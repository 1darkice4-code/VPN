CREATE TABLE IF NOT EXISTS vpn_profiles (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(telegram_id),
    vpn_type VARCHAR(50),
    config TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
