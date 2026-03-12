-- SEED SIMPLE POUR TESTS API
-- Insertion directe des utilisateurs de test

-- Nettoyer les données existantes
DELETE FROM audit_logs;
DELETE FROM refresh_tokens;
DELETE FROM users;

-- Utilisateurs de test avec mots de passe hashés bcrypt
-- Tous les mots de passe sont : [role]123! (ex: Admin123!, Notaire123!)

INSERT INTO users (id, email, password_hash, role, is_active, is_verified, failed_login_count, created_at, updated_at) VALUES
(
    gen_random_uuid(),
    'admin@test.fr',
    '$2b$12$8XGp9Xx.ZQF2eFq5V5jF5.Cb0qU8QqXGzYn9GDW8xyKgBHxNJaEd6', -- Admin123!
    'admin',
    true,
    true,
    0,
    NOW(),
    NOW()
),
(
    gen_random_uuid(),
    'notaire1@test.fr',
    '$2b$12$Y7EaRkJ1mGGiF8FNyJJjVu/YtH5z7GXNq2KNVk8X1Yr5LFQEGzPiK', -- Notaire123!
    'notaire',
    true,
    true,
    0,
    NOW(),
    NOW()
),
(
    gen_random_uuid(),
    'clerc@test.fr',
    '$2b$12$HZPDqj2LGhNPxM7KXzLBrO.C8GNZQgPFsZzGVjKVLq7DQA2RhEcQm', -- Clerc123!
    'clerc',
    true,
    true,
    0,
    NOW(),
    NOW()
),
(
    gen_random_uuid(),
    'client@test.fr',
    '$2b$12$JGPRt4Y2GzFSUxP7VZfKHuRtS5hGsVLmN7WqXM2BN8YLhKQtG4T9W', -- Client123!
    'client',
    true,
    true,
    0,
    NOW(),
    NOW()
),
(
    gen_random_uuid(),
    'unverified@test.fr',
    '$2b$12$NKPcZ8V3FxLKGj7TZqVkM.aR6hVKJL9SdJK7VHqN2A4GQr9WL8XcO', -- Test123!
    'client',
    true,
    false, -- Non vérifié pour tests
    0,
    NOW(),
    NOW()
);

-- Afficher les comptes créés
SELECT
    email,
    role,
    is_verified,
    CASE
        WHEN is_verified THEN '✅ Vérifié'
        ELSE '❌ Non vérifié'
    END as status
FROM users
ORDER BY role, email;