-- Least-privilege grants for the read-only API role.
GRANT USAGE ON SCHEMA public TO relay_app;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO relay_app;
ALTER DEFAULT PRIVILEGES FOR ROLE relay_admin IN SCHEMA public GRANT SELECT ON TABLES TO relay_app;
