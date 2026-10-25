-- Synthetic migration fixture for an isolated PostgreSQL test database only.
INSERT INTO users (id, email, role, is_active)
VALUES
('00000000-0000-4000-8000-000000000101', 'legacy-owner@example.invalid', 'MerchantOwner', true),
('00000000-0000-4000-8000-000000000102', 'legacy-customer@example.invalid', 'Customer', true);
INSERT INTO customer_profiles (id, user_id, full_name)
VALUES ('00000000-0000-4000-8000-000000000103', '00000000-0000-4000-8000-000000000102', 'Legacy Customer');
INSERT INTO merchants (id, owner_user_id, business_name, legal_entity_name, fssai_license_number, status)
VALUES ('00000000-0000-4000-8000-000000000104', '00000000-0000-4000-8000-000000000101', 'Legacy Merchant', 'Legacy Merchant', '12345678901234', 'APPROVED');
INSERT INTO brands (id, merchant_id, name)
VALUES ('00000000-0000-4000-8000-000000000105', '00000000-0000-4000-8000-000000000104', 'Legacy Brand');
INSERT INTO branches (id, brand_id, name, address_text)
VALUES ('00000000-0000-4000-8000-000000000106', '00000000-0000-4000-8000-000000000105', 'Legacy Branch', 'Test Lane');
INSERT INTO orders (id, customer_profile_id, branch_id, total_amount, status, delivery_address_snapshot)
VALUES ('00000000-0000-4000-8000-000000000107', '00000000-0000-4000-8000-000000000103', '00000000-0000-4000-8000-000000000106', 42.50, 'PLACED', '{"address_line":"Synthetic"}'::jsonb);
