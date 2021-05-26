-- Initialization script
-- Creates the database and tables

-- This is not needed as the suer and database are created from the docker
-- compose environment variables
CREATE USER sdv_summary WITH PASSWORD 'sdv_summary';
CREATE DATABASE sdv_summary_development;
GRANT ALL PRIVILEGES ON DATABASE sdv_summary_development TO sdv_summary;
