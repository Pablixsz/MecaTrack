-- ============================================
-- SEED DATA - Datos de prueba para desarrollo
-- ============================================

-- 1. USERS (4 usuarios: owner, mechanic, client, admin)
--    Contrasena de TODOS: test1234 (solo datos de prueba, publica a proposito).
--    El hash es scrypt de werkzeug.security.generate_password_hash('test1234'),
--    el mismo formato que usa la app al registrar; asi el login funciona en una base nueva.
INSERT INTO users (first_name, middle_name, last_name, second_last_name, document_number, email, role, password_hash, phone, status)
VALUES
('Carlos', NULL, 'Ramirez', 'Gomez', '1001234567', 'carlos.owner@tallermecanico.com', 'owner', 'scrypt:32768:8:1$HA3JPLlUGNkODLGM$3cb2543a2fa349d898f1ad3f64adcfa4a815c2920816a253ea30d52a8262fcf5b899e423b428b1ef866bb7d089d4b641edc6e0ccf2b7f6beb7523ca1a784e021', '3001234567', 'active'),
('Andres', NULL, 'Torres', 'Lopez', '1002345678', 'andres.mecanico@tallermecanico.com', 'mechanic', 'scrypt:32768:8:1$HA3JPLlUGNkODLGM$3cb2543a2fa349d898f1ad3f64adcfa4a815c2920816a253ea30d52a8262fcf5b899e423b428b1ef866bb7d089d4b641edc6e0ccf2b7f6beb7523ca1a784e021', '3012345678', 'active'),
('Laura', 'Maria', 'Gonzalez', 'Diaz', '1003456789', 'laura.cliente@gmail.com', 'client', 'scrypt:32768:8:1$HA3JPLlUGNkODLGM$3cb2543a2fa349d898f1ad3f64adcfa4a815c2920816a253ea30d52a8262fcf5b899e423b428b1ef866bb7d089d4b641edc6e0ccf2b7f6beb7523ca1a784e021', '3023456789', 'active'),
('Ana', NULL, 'Martinez', 'Rojas', '1004567890', 'admin@tallermecanico.com', 'admin', 'scrypt:32768:8:1$HA3JPLlUGNkODLGM$3cb2543a2fa349d898f1ad3f64adcfa4a815c2920816a253ea30d52a8262fcf5b899e423b428b1ef866bb7d089d4b641edc6e0ccf2b7f6beb7523ca1a784e021', '3034567890', 'active');

-- 2. BUSINESSES (1 negocio, dueño = Carlos)
INSERT INTO businesses (business_name, tax_id, address, business_phone, business_registration_number, legal_documents_verified, owner_user_id)
VALUES
('Taller Mecanico El Motor', '900123456-7', 'Calle 45 # 12-34, Bogota', '6011234567', 'RM-2024-00123', TRUE, 1);

-- 3. VEHICLES (2 vehiculos, propietario = Laura, user_id 3)
INSERT INTO vehicles (owner_user_id, license_plate, brand, model, year, color, vehicle_type, vin, engine_displacement, mileage, fuel_type, transmission_type)
VALUES
(3, 'ABC123', 'Mazda', '3', 2020, 'Rojo', 'car', '1HGCM82633A123456', 2.00, 45000, 'gasoline', 'automatic'),
(3, 'XYZ789', 'Yamaha', 'FZ', 2022, 'Negro', 'motorcycle', NULL, 150.00, 8000, 'gasoline', 'manual');

-- 4. BAYS (2 bahias del negocio)
INSERT INTO bays (business_id, bay_number, has_elevator, status)
VALUES
(1, 'Bahia 1', TRUE, 'available'),
(1, 'Bahia 2', FALSE, 'available');

-- 5. SERVICES (12 servicios del catalogo; del 3 al 12 se agregaron para la
--    Guia 5, ver database/catalog.sql para cargarlos en una base existente)
INSERT INTO services (business_id, service_name, description, estimated_duration_minutes, base_price, status)
VALUES
(1, 'Cambio de aceite', 'Cambio de aceite y filtro', 45, 80000, 'active'),
(1, 'Alineacion y balanceo', 'Alineacion de llantas y balanceo', 60, 120000, 'active'),
(1, 'Cambio de pastillas de freno', 'Reemplazo de pastillas de freno y revision del liquido de frenos', 90, 180000, 'active'),
(1, 'Rectificación de discos de freno', 'Rectificado o cambio de discos de freno alabeados que causan vibracion al frenar', 120, 220000, 'active'),
(1, 'Revisión de suspensión', 'Revision y cambio de amortiguadores, bujes, terminales y rotulas', 120, 250000, 'active'),
(1, 'Sincronización de motor', 'Cambio de bujias, limpieza de inyectores y ajuste de la mezcla aire-combustible', 120, 280000, 'active'),
(1, 'Diagnóstico con escáner', 'Lectura de codigos de falla de la computadora del vehiculo (check engine)', 45, 90000, 'active'),
(1, 'Revisión de batería y sistema eléctrico', 'Prueba de bateria, alternador y motor de arranque', 60, 100000, 'active'),
(1, 'Mantenimiento de aire acondicionado', 'Recarga de gas refrigerante, limpieza del evaporador y cambio del filtro de cabina', 90, 200000, 'active'),
(1, 'Revisión de embrague', 'Ajuste o cambio del kit de embrague (disco, prensa y balinera)', 240, 650000, 'active'),
(1, 'Mantenimiento del sistema de refrigeración', 'Cambio de refrigerante y revision de radiador, termostato y mangueras', 90, 170000, 'active'),
(1, 'Cambio de correa de distribución', 'Reemplazo del kit de correa de distribucion y bomba de agua', 240, 550000, 'active');

-- 6. APPOINTMENTS (1 cita: Laura agenda con su Mazda, mecanico Andres)
INSERT INTO appointments (client_user_id, vehicle_id, service_id, bay_id, mechanic_user_id, scheduled_start, scheduled_end, status)
VALUES
(3, 1, 1, 1, 2, '2026-09-15 09:00:00', '2026-09-15 09:45:00', 'confirmed');

-- 7. PAYMENTS (2 pagos: deposito ya pagado, saldo pendiente)
INSERT INTO payments (appointment_id, payment_type, payment_method, amount, status, paid_at)
VALUES
(1, 'deposit', 'transfer', 30000, 'completed', '2026-09-13 10:00:00'),
(1, 'balance', 'cash', 50000, 'pending', NULL);

-- 8. PARTS (1 repuesto en inventario)
INSERT INTO parts (business_id, part_name, unit_price, stock_quantity, status)
VALUES
(1, 'Filtro de aceite', 15000, 20, 'active');

-- 9. SERVICE_TRACKING (1 registro de seguimiento de la cita)
INSERT INTO service_tracking (appointment_id, status, notes, current_mileage)
VALUES
(1, 'received', 'Vehiculo recibido, sin daños visibles', 45000);

-- 10. SERVICE_TRACKING_PARTS (repuesto usado en ese seguimiento)
INSERT INTO service_tracking_parts (tracking_id, part_id, quantity)
VALUES
(1, 1, 1);