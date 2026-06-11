-- Run this SQL script to set up the database manually if needed

CREATE DATABASE IF NOT EXISTS inventory_system;
USE inventory_system;

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('owner', 'assistant') NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    id INT AUTO_INCREMENT PRIMARY KEY,
    product_name VARCHAR(100) NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS inventory_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    product_id INT NOT NULL,
    quantity_change INT NOT NULL,
    cost_price DECIMAL(10,2),
    selling_price DECIMAL(10,2),
    log_type ENUM('sale', 'restock') NOT NULL,
    recorded_by VARCHAR(50) NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(id)
);

-- Insert default owner account (password: admin123)
INSERT IGNORE INTO users (username, password_hash, role) 
VALUES ('owner', 'pbkdf2:sha256:260000$salt$hash', 'owner');

-- Sample assistant account (password: assistant123)
INSERT IGNORE INTO users (username, password_hash, role) 
VALUES ('assistant', 'pbkdf2:sha256:260000$salt$hash', 'assistant');