"""Generate 10,000 synthetic transaction records for PEIT demonstration.

Covers 10 canonical expenditure categories over 60 months (2021-01 to 2025-12)
with 3% compound annual inflation, and includes explicit pedagogical demonstration
scenarios:
  1. Price increase with unchanged quantity (Milk 25.00 -> 28.00)
  2. Quantity increase without price increase (Bread 1 -> 2 @ 10.00)
  3. Brand substitution via item_normalized (Milk Brand A -> Milk Brand B)
  4. Signed discount convention (Detergent 80.00 - 10.00 = -70.00)
  5. Fee, tax, and deposit adjustments (fee: -5.00, tax: -8.00 -> -113.00)
  6. Non-purchase ledger events (income, transfer, refund)
"""

from __future__ import annotations

import csv
import math
from pathlib import Path


# Comprehensive catalog across 10 categories + ledger exclusions
CATALOG = [
    # 1. Food and beverages (Groceries, Produce, Meat, Pantry, Dining)
    {"merchant": "Supermercado Central", "item_raw": "Leche Entera Pasteurizada 1L", "item_normalized": "milk 1 l",
     "category": "Food and beverages", "unit": "L", "base_price": 25.00, "event_type": "recurring", "base_qty": 1, "volatility": 0.015},
    {"merchant": "Supermercado Central", "item_raw": "Pan Blanco de Caja 500g", "item_normalized": "white bread 500 g",
     "category": "Food and beverages", "unit": "piece", "base_price": 10.00, "event_type": "recurring", "base_qty": 1, "volatility": 0.0},
    {"merchant": "Supermercado Central", "item_raw": "Huevos Blancos Docena", "item_normalized": "eggs 12 pack",
     "category": "Food and beverages", "unit": "piece", "base_price": 42.00, "event_type": "recurring", "base_qty": 2, "volatility": 0.03},
    {"merchant": "Supermercado Central", "item_raw": "Café Tostado y Molido 250g", "item_normalized": "ground coffee 250 g", "category": "Food and beverages",
     "unit": "piece", "base_price": 85.80, "event_type": "recurring", "base_qty": 1, "volatility": 0.02, "has_discount": True},
    {"merchant": "Supermercado Central", "item_raw": "Arroz Grano Largo 1kg", "item_normalized": "rice long grain 1 kg",
     "category": "Food and beverages", "unit": "kg", "base_price": 28.50, "event_type": "recurring", "base_qty": 2, "volatility": 0.01},
    {"merchant": "Supermercado Central", "item_raw": "Frijol Negro 1kg", "item_normalized": "black beans 1 kg",
     "category": "Food and beverages", "unit": "kg", "base_price": 34.00, "event_type": "recurring", "base_qty": 2, "volatility": 0.015},
    {"merchant": "Supermercado Central", "item_raw": "Pechuga de Pollo Fresca 1kg", "item_normalized": "chicken breast fresh 1 kg",
     "category": "Food and beverages", "unit": "kg", "base_price": 125.00, "event_type": "recurring", "base_qty": 2, "volatility": 0.04},
    {"merchant": "Supermercado Central", "item_raw": "Bistec de Res 1kg", "item_normalized": "beef steak 1 kg",
     "category": "Food and beverages", "unit": "kg", "base_price": 195.00, "event_type": "recurring", "base_qty": 1, "volatility": 0.035},
    {"merchant": "Supermercado Central", "item_raw": "Filete de Pescado Blanco 500g", "item_normalized": "fish fillet white 500 g",
     "category": "Food and beverages", "unit": "g", "base_price": 95.00, "event_type": "recurring", "base_qty": 1, "volatility": 0.03},
    {"merchant": "Supermercado Central", "item_raw": "Manzana Gala 1kg", "item_normalized": "apples gala 1 kg",
     "category": "Food and beverages", "unit": "kg", "base_price": 45.00, "event_type": "recurring", "base_qty": 2, "volatility": 0.05},
    {"merchant": "Supermercado Central", "item_raw": "Plátano Tabasco 1kg", "item_normalized": "banana tabasco 1 kg",
     "category": "Food and beverages", "unit": "kg", "base_price": 22.00, "event_type": "recurring", "base_qty": 2, "volatility": 0.04},
    {"merchant": "Supermercado Central", "item_raw": "Aguacate Hass 1kg", "item_normalized": "avocado hass 1 kg",
     "category": "Food and beverages", "unit": "kg", "base_price": 68.00, "event_type": "recurring", "base_qty": 1, "volatility": 0.08},
    {"merchant": "Supermercado Central", "item_raw": "Jitomate Saladet 1kg", "item_normalized": "tomato saladet 1 kg",
     "category": "Food and beverages", "unit": "kg", "base_price": 32.00, "event_type": "recurring", "base_qty": 2, "volatility": 0.07},
    {"merchant": "Supermercado Central", "item_raw": "Aceite Vegetal Comestible 1L", "item_normalized": "vegetable oil 1 l",
     "category": "Food and beverages", "unit": "L", "base_price": 46.00, "event_type": "recurring", "base_qty": 1, "volatility": 0.03},
    {"merchant": "Supermercado Central", "item_raw": "Garrafón de Agua Purificada 20L", "item_normalized": "water jug 20 l",
     "category": "Food and beverages", "unit": "piece", "base_price": 50.00, "event_type": "recurring", "base_qty": 1, "volatility": 0.01, "deposit": -20.00},
    {"merchant": "Restaurante Local", "item_raw": "Almuerzo Menú Ejecutivo", "item_normalized": "restaurant lunch special",
     "category": "Food and beverages", "unit": "piece", "base_price": 135.00, "event_type": "one_off", "base_qty": 1, "volatility": 0.02},
    {"merchant": "Cafetería Urbana", "item_raw": "Café Americano Grande", "item_normalized": "coffee americano large",
     "category": "Food and beverages", "unit": "piece", "base_price": 48.00, "event_type": "one_off", "base_qty": 1, "volatility": 0.02},

    # 2. Energy (Electricity, LPG Gas, Gasoline)
    {"merchant": "CFE Suministrador", "item_raw": "Suministro Eléctrico Tarifa 1", "item_normalized": "electricity residential",
     "category": "Energy", "unit": "kWh", "base_price": 1.80, "event_type": "recurring", "base_qty": 160, "volatility": 0.01},
    {"merchant": "Gasera Residencial", "item_raw": "Gas LP Estacionario Litro", "item_normalized": "lpg residential bulk 1 l",
     "category": "Energy", "unit": "L", "base_price": 12.50, "event_type": "recurring", "base_qty": 80, "volatility": 0.04},
    {"merchant": "Estación Servicio Gas", "item_raw": "Gasolina Regular 87 Octanos", "item_normalized": "gasoline regular 87 1 l",
     "category": "Energy", "unit": "L", "base_price": 22.00, "event_type": "recurring", "base_qty": 40, "volatility": 0.025},
    {"merchant": "Estación Servicio Gas", "item_raw": "Gasolina Premium 91 Octanos", "item_normalized": "gasoline premium 91 1 l",
     "category": "Energy", "unit": "L", "base_price": 24.20, "event_type": "recurring", "base_qty": 40, "volatility": 0.025},

    # 3. Medical care (Prescription, OTC, Doctor, Dental)
    {"merchant": "Farmacia del Ahorro", "item_raw": "Metformina 850mg 30 Tabletas", "item_normalized": "metformin 850 mg 30 tab",
     "category": "Medical care", "unit": "piece", "base_price": 120.00, "event_type": "recurring", "base_qty": 1, "volatility": 0.01},
    {"merchant": "Farmacia del Ahorro", "item_raw": "Paracetamol 500mg 20 Tabletas", "item_normalized": "paracetamol 500 mg 20 tab",
     "category": "Medical care", "unit": "piece", "base_price": 45.00, "event_type": "recurring", "base_qty": 1, "volatility": 0.01},
    {"merchant": "Farmacia del Ahorro", "item_raw": "Antigripal Multisíntomas 12 Cápsulas", "item_normalized": "cold flu relief 12 cap",
     "category": "Medical care", "unit": "piece", "base_price": 98.00, "event_type": "one_off", "base_qty": 1, "volatility": 0.015},
    {"merchant": "Consultorio Médico", "item_raw": "Consulta Medicina General", "item_normalized": "doctor visit general",
     "category": "Medical care", "unit": "piece", "base_price": 500.00, "event_type": "one_off", "base_qty": 1, "volatility": 0.02},
    {"merchant": "Clínica Dental", "item_raw": "Limpieza Dental Semestral", "item_normalized": "dental cleaning routine",
     "category": "Medical care", "unit": "piece", "base_price": 850.00, "event_type": "one_off", "base_qty": 1, "volatility": 0.02},

    # 4. Education and communication (Internet, Mobile, Cloud, Courses)
    {"merchant": "Telecomunicaciones Fibra", "item_raw": "Internet Fibra Óptica 100Mbps", "item_normalized": "fiber internet 100 mbps",
     "category": "Education and communication", "unit": "piece", "base_price": 450.00, "event_type": "recurring", "base_qty": 1, "volatility": 0.0},
    {"merchant": "Telefonía Móvil", "item_raw": "Plan Celular Prepago 30 Días", "item_normalized": "mobile plan prepaid 30 days",
     "category": "Education and communication", "unit": "piece", "base_price": 200.00, "event_type": "recurring", "base_qty": 1, "volatility": 0.0},
    {"merchant": "Servicios Cloud", "item_raw": "Almacenamiento Cloud 100GB Mes", "item_normalized": "cloud storage 100 gb month",
     "category": "Education and communication", "unit": "piece", "base_price": 49.00, "event_type": "recurring", "base_qty": 1, "volatility": 0.01},
    {"merchant": "Instituto Lenguas", "item_raw": "Mensualidad Curso de Idiomas", "item_normalized": "language course tuition month",
     "category": "Education and communication", "unit": "piece", "base_price": 1400.00, "event_type": "recurring", "base_qty": 1, "volatility": 0.01},
    {"merchant": "Librería Académica", "item_raw": "Libro de Texto Universitario", "item_normalized": "textbook academic print",
     "category": "Education and communication", "unit": "piece", "base_price": 650.00, "event_type": "one_off", "base_qty": 1, "volatility": 0.02},

    # 5. Housing (Rent, Maintenance, Water, Cleaning, Discounted detergent)
    {"merchant": "Inmobiliaria Residencial", "item_raw": "Renta Mensual Departamento", "item_normalized": "residential rent apartment",
     "category": "Housing", "unit": "piece", "base_price": 8500.00, "event_type": "recurring", "base_qty": 1, "volatility": 0.0},
    {"merchant": "Administración Condominio", "item_raw": "Cuota Mantenimiento Edificio", "item_normalized": "building maintenance monthly",
     "category": "Housing", "unit": "piece", "base_price": 1100.00, "event_type": "recurring", "base_qty": 1, "volatility": 0.0},
    {"merchant": "Sistema de Aguas", "item_raw": "Servicio de Agua Potable y Drenaje", "item_normalized": "municipal water supply",
     "category": "Housing", "unit": "piece", "base_price": 260.00, "event_type": "recurring", "base_qty": 1, "volatility": 0.01},
    {"merchant": "Supermercado Central", "item_raw": "Detergente Líquido 1L", "item_normalized": "laundry detergent 1 l",
     "category": "Housing", "unit": "L", "base_price": 80.00, "event_type": "recurring", "base_qty": 1, "volatility": 0.01, "special_discount": 10.00},
    {"merchant": "Ferretería Local", "item_raw": "Foco LED A19 9W Luz Cálida", "item_normalized": "led light bulb 9w",
     "category": "Housing", "unit": "piece", "base_price": 38.00, "event_type": "one_off", "base_qty": 2, "volatility": 0.02},

    # 6. Transportation (Metro, Ride-hailing, Parking, Tolls, Auto Service)
    {"merchant": "Sistema Metro Urbano", "item_raw": "Recarga Tarjeta Transporte 10 Viajes", "item_normalized": "transit card 10 rides pass",
     "category": "Transportation", "unit": "piece", "base_price": 50.00, "event_type": "recurring", "base_qty": 1, "volatility": 0.0},
    {"merchant": "App Taxi Movilidad", "item_raw": "Viaje Taxi Urbano 5km", "item_normalized": "ride hailing trip urban 5km",
     "category": "Transportation", "unit": "piece", "base_price": 85.00, "event_type": "one_off", "base_qty": 1, "volatility": 0.05},
    {"merchant": "Estacionamiento Plaza", "item_raw": "Estacionamiento Centro Comercial 2h", "item_normalized": "parking fee 2 hours",
     "category": "Transportation", "unit": "hour", "base_price": 40.00, "event_type": "one_off", "base_qty": 1, "volatility": 0.02},
    {"merchant": "Autopistas Concesionadas", "item_raw": "Peaje Caseta Autopista", "item_normalized": "highway toll standard",
     "category": "Transportation", "unit": "piece", "base_price": 75.00, "event_type": "one_off", "base_qty": 1, "volatility": 0.01},
    {"merchant": "Taller Mecánico", "item_raw": "Servicio Cambio de Aceite y Filtro", "item_normalized": "vehicle oil change service",
     "category": "Transportation", "unit": "piece", "base_price": 950.00, "event_type": "one_off", "base_qty": 1, "volatility": 0.02},

    # 7. Recreation (Streaming, Gym, Cinema, Pets, Books)
    {"merchant": "Servicio Streaming Plus", "item_raw": "Suscripción Video Streaming Mes", "item_normalized": "video streaming monthly",
     "category": "Recreation", "unit": "piece", "base_price": 199.00, "event_type": "recurring", "base_qty": 1, "volatility": 0.0},
    {"merchant": "Servicio Música Beat", "item_raw": "Suscripción Música Streaming Mes", "item_normalized": "music streaming monthly",
     "category": "Recreation", "unit": "piece", "base_price": 129.00, "event_type": "recurring", "base_qty": 1, "volatility": 0.0},
    {"merchant": "Gimnasio Fitness Center", "item_raw": "Mensualidad Gimnasio Acceso Total", "item_normalized": "gym membership monthly",
     "category": "Recreation", "unit": "piece", "base_price": 690.00, "event_type": "recurring", "base_qty": 1, "volatility": 0.01},
    {"merchant": "Cineplex Plaza", "item_raw": "Boleto Entrada Cine Tradicional", "item_normalized": "cinema movie ticket",
     "category": "Recreation", "unit": "piece", "base_price": 85.00, "event_type": "one_off", "base_qty": 2, "volatility": 0.02},
    {"merchant": "Tienda Mascotas", "item_raw": "Alimento Seco Perro Adulto 15kg", "item_normalized": "dog food dry adult 15 kg",
     "category": "Recreation", "unit": "kg", "base_price": 780.00, "event_type": "recurring", "base_qty": 1, "volatility": 0.025},

    # 8. Apparel (Outerwear, Footwear, Tailor, Dry cleaning)
    {"merchant": "Boutique Ropa Casual", "item_raw": "Camisa Casual Algodón Manga Larga", "item_normalized": "shirt casual cotton long sleeve",
     "category": "Apparel", "unit": "piece", "base_price": 450.00, "event_type": "one_off", "base_qty": 1, "volatility": 0.03, "has_discount": True},
    {"merchant": "Tienda Departamental", "item_raw": "Pantalón de Mezclilla Jeans", "item_normalized": "jeans denim pants",
     "category": "Apparel", "unit": "piece", "base_price": 650.00, "event_type": "one_off", "base_qty": 1, "volatility": 0.02},
    {"merchant": "Zapatería Deportiva", "item_raw": "Tenis Deportivos para Correr", "item_normalized": "shoes running athletic",
     "category": "Apparel", "unit": "piece", "base_price": 1250.00, "event_type": "one_off", "base_qty": 1, "volatility": 0.03},
    {"merchant": "Tintorería Ecológica", "item_raw": "Tintorería Lavado y Planchado Traje", "item_normalized": "dry cleaning suit 2 piece",
     "category": "Apparel", "unit": "piece", "base_price": 180.00, "event_type": "one_off", "base_qty": 1, "volatility": 0.02},

    # 9. Other goods (Hygiene, Cosmetics, Sundries, Hardware)
    {"merchant": "Supermercado Central", "item_raw": "Pasta Dental Anticaries 100mL", "item_normalized": "toothpaste anticavity 100 ml",
     "category": "Other goods", "unit": "piece", "base_price": 38.00, "event_type": "recurring", "base_qty": 1, "volatility": 0.015},
    {"merchant": "Supermercado Central", "item_raw": "Jabón de Tocador en Barra 125g", "item_normalized": "body soap bar 125 g",
     "category": "Other goods", "unit": "piece", "base_price": 18.00, "event_type": "recurring", "base_qty": 2, "volatility": 0.01},
    {"merchant": "Supermercado Central", "item_raw": "Champú Cuidado Diario 400mL", "item_normalized": "shampoo daily care 400 ml",
     "category": "Other goods", "unit": "piece", "base_price": 72.00, "event_type": "recurring", "base_qty": 1, "volatility": 0.02},
    {"merchant": "Supermercado Central", "item_raw": "Papel Higiénico 12 Rollos", "item_normalized": "toilet paper 12 pack",
     "category": "Other goods", "unit": "piece", "base_price": 95.00, "event_type": "recurring", "base_qty": 1, "volatility": 0.02},
    {"merchant": "Supermercado Central", "item_raw": "Pilas Alcalinas AA Paquete 4 Pzas", "item_normalized": "batteries alkaline aa 4 pack",
     "category": "Other goods", "unit": "piece", "base_price": 85.00, "event_type": "one_off", "base_qty": 1, "volatility": 0.02},

    # 10. Other services (Barber, Bank, Delivery Fee with Multi-Component Adjustments)
    {"merchant": "Barbería Tradicional", "item_raw": "Corte de Cabello Caballero", "item_normalized": "haircut men standard",
     "category": "Other services", "unit": "piece", "base_price": 150.00, "event_type": "recurring", "base_qty": 1, "volatility": 0.01},
    {"merchant": "Banco Financiero", "item_raw": "Comisión Mensual Manejo de Cuenta", "item_normalized": "bank account maintenance fee",
     "category": "Other services", "unit": "piece", "base_price": 65.00, "event_type": "recurring", "base_qty": 1, "volatility": 0.0},
    {"merchant": "App Delivery Express", "item_raw": "Pedido Restaurante con Entrega", "item_normalized": "prepared meal delivery",
     "category": "Other services", "unit": "piece", "base_price": 100.00, "event_type": "one_off", "base_qty": 1, "volatility": 0.02, "fee": -5.00, "tax": -8.00},
]


def generate_rows(target_count: int = 10000) -> list[dict[str, str]]:
    """Generate exactly 10,000 realistic receipt rows over 60 months."""
    rows: list[dict[str, str]] = []
    months = [f"{2021 + t // 12:04d}-{1 + (t % 12):02d}" for t in range(60)]
    row_id_counter = 1

    # First, insert explicit pedagogical demonstration scenarios into 2021-01 and 2021-02
    # ----------------------------------------------------------------------------------
    # Month 1: 2021-01 Demo Scenarios
    # Scenario 1: Milk 1 L at MXN 25.00
    rows.append({
        "month": "2021-01", "receipt_id": f"REC-202101-{row_id_counter:05d}", "receipt_date": "2021-01-05",
        "merchant": "Supermercado Central", "item_raw": "Leche Entera 1L", "item_normalized": "milk 1 l",
        "category": "Food and beverages", "quantity": "1", "unit": "L", "shelf_unit_price": "25.00",
        "currency": "MXN", "discount": "0", "fee": "0", "tax": "0", "deposit": "0", "paid_total": "-25.00",
        "event_type": "recurring", "source_file": "example_month.csv", "notes": "Scenario 1: Price increase base (Milk 25.00)",
    })
    row_id_counter += 1

    # Scenario 2: Bread 1 piece at MXN 10.00
    rows.append({
        "month": "2021-01", "receipt_id": f"REC-202101-{row_id_counter:05d}", "receipt_date": "2021-01-05",
        "merchant": "Panadería Tradicional", "item_raw": "Pan Blanco 500g", "item_normalized": "white bread 500 g",
        "category": "Food and beverages", "quantity": "1", "unit": "piece", "shelf_unit_price": "10.00",
        "currency": "MXN", "discount": "0", "fee": "0", "tax": "0", "deposit": "0", "paid_total": "-10.00",
        "event_type": "recurring", "source_file": "example_month.csv", "notes": "Scenario 2: Quantity increase base (1 piece)",
    })
    row_id_counter += 1

    # Scenario 3: Milk brand A, 1 L -> item_normalized: milk 1 l
    rows.append({
        "month": "2021-01", "receipt_id": f"REC-202101-{row_id_counter:05d}", "receipt_date": "2021-01-10",
        "merchant": "Supermercado Central", "item_raw": "Leche Marca A 1L", "item_normalized": "milk 1 l",
        "category": "Food and beverages", "quantity": "1", "unit": "L", "shelf_unit_price": "25.00",
        "currency": "MXN", "discount": "0", "fee": "0", "tax": "0", "deposit": "0", "paid_total": "-25.00",
        "event_type": "recurring", "source_file": "example_month.csv", "notes": "Scenario 3: Substitution Brand A",
    })
    row_id_counter += 1

    # Scenario 4: Detergent shelf = 80.00, discount = 10.00, paid total = -70.00
    rows.append({
        "month": "2021-01", "receipt_id": f"REC-202101-{row_id_counter:05d}", "receipt_date": "2021-01-12",
        "merchant": "Supermercado Central", "item_raw": "Detergente Líquido 1L", "item_normalized": "laundry detergent 1 l",
        "category": "Housing", "quantity": "1", "unit": "L", "shelf_unit_price": "80.00",
        "currency": "MXN", "discount": "10.00", "fee": "0", "tax": "0", "deposit": "0", "paid_total": "-70.00",
        "event_type": "recurring", "source_file": "example_month.csv", "notes": "Scenario 4: Signed discount (80 - 10 = -70)",
    })
    row_id_counter += 1

    # Scenario 5: Fee, tax, or deposit (fee = -5.00, tax = -8.00, deposit = 0.00)
    rows.append({
        "month": "2021-01", "receipt_id": f"REC-202101-{row_id_counter:05d}", "receipt_date": "2021-01-15",
        "merchant": "App Delivery Express", "item_raw": "Pedido Restaurante con Entrega", "item_normalized": "prepared meal delivery",
        "category": "Other services", "quantity": "1", "unit": "piece", "shelf_unit_price": "100.00",
        "currency": "MXN", "discount": "0", "fee": "-5.00", "tax": "-8.00", "deposit": "0", "paid_total": "-113.00",
        "event_type": "one_off", "source_file": "example_month.csv", "notes": "Scenario 5: Multi-component adjustment (fee -5, tax -8)",
    })
    row_id_counter += 1

    # Scenario 6: Non-purchase ledger events (income, transfer, refund)
    rows.append({
        "month": "2021-01", "receipt_id": f"REC-202101-{row_id_counter:05d}", "receipt_date": "2021-01-20",
        "merchant": "Familia", "item_raw": "Apoyo Familiar", "item_normalized": "family financial support",
        "category": "Transfers and gifts", "quantity": "1", "unit": "piece", "shelf_unit_price": "3000.00",
        "currency": "MXN", "discount": "0", "fee": "0", "tax": "0", "deposit": "0", "paid_total": "3000.00",
        "event_type": "income", "source_file": "example_month.csv", "notes": "Scenario 6a: Income non-consumption ledger row",
    })
    row_id_counter += 1
    rows.append({
        "month": "2021-01", "receipt_id": f"REC-202101-{row_id_counter:05d}", "receipt_date": "2021-01-22",
        "merchant": "Banco Financiero", "item_raw": "Transferencia entre Cuentas", "item_normalized": "inter account transfer",
        "category": "Financial movements", "quantity": "1", "unit": "piece", "shelf_unit_price": "500.00",
        "currency": "MXN", "discount": "0", "fee": "0", "tax": "0", "deposit": "0", "paid_total": "-500.00",
        "event_type": "transfer", "source_file": "example_month.csv", "notes": "Scenario 6b: Financial transfer row",
    })
    row_id_counter += 1
    rows.append({
        "month": "2021-01", "receipt_id": f"REC-202101-{row_id_counter:05d}", "receipt_date": "2021-01-25",
        "merchant": "Tienda Departamental", "item_raw": "Reembolso Ropa", "item_normalized": "apparel refund",
        "category": "Apparel", "quantity": "1", "unit": "piece", "shelf_unit_price": "250.00",
        "currency": "MXN", "discount": "0", "fee": "0", "tax": "0", "deposit": "0", "paid_total": "250.00",
        "event_type": "refund", "source_file": "example_month.csv", "notes": "Scenario 6c: Refund credit offset",
    })
    row_id_counter += 1

    # Month 2: 2021-02 Paired Demo Scenarios
    # Scenario 1 follow-up: Milk 1 L at MXN 28.00
    rows.append({
        "month": "2021-02", "receipt_id": f"REC-202102-{row_id_counter:05d}", "receipt_date": "2021-02-05",
        "merchant": "Supermercado Central", "item_raw": "Leche Entera 1L", "item_normalized": "milk 1 l",
        "category": "Food and beverages", "quantity": "1", "unit": "L", "shelf_unit_price": "28.00",
        "currency": "MXN", "discount": "0", "fee": "0", "tax": "0", "deposit": "0", "paid_total": "-28.00",
        "event_type": "recurring", "source_file": "example_month.csv", "notes": "Scenario 1: Price increase result (Milk 28.00)",
    })
    row_id_counter += 1

    # Scenario 2 follow-up: Bread 2 pieces at MXN 10.00 each
    rows.append({
        "month": "2021-02", "receipt_id": f"REC-202102-{row_id_counter:05d}", "receipt_date": "2021-02-05",
        "merchant": "Panadería Tradicional", "item_raw": "Pan Blanco 500g", "item_normalized": "white bread 500 g",
        "category": "Food and beverages", "quantity": "2", "unit": "piece", "shelf_unit_price": "10.00",
        "currency": "MXN", "discount": "0", "fee": "0", "tax": "0", "deposit": "0", "paid_total": "-20.00",
        "event_type": "recurring", "source_file": "example_month.csv", "notes": "Scenario 2: Quantity increase (2 pieces @ 10.00)",
    })
    row_id_counter += 1

    # Scenario 3 follow-up: Milk brand B, 1 L -> item_normalized: milk 1 l
    rows.append({
        "month": "2021-02", "receipt_id": f"REC-202102-{row_id_counter:05d}", "receipt_date": "2021-02-10",
        "merchant": "Supermercado Central", "item_raw": "Leche Marca B 1L", "item_normalized": "milk 1 l",
        "category": "Food and beverages", "quantity": "1", "unit": "L", "shelf_unit_price": "26.00",
        "currency": "MXN", "discount": "0", "fee": "0", "tax": "0", "deposit": "0", "paid_total": "-26.00",
        "event_type": "recurring", "source_file": "example_month.csv", "notes": "Scenario 3: Substitution Brand B",
    })
    row_id_counter += 1

    # Main catalog generation across 60 months
    while len(rows) < target_count:
        for t, month_str in enumerate(months):
            if len(rows) >= target_count:
                break

            inflation_factor = (1.03) ** (t / 12.0)
            m_num = 1 + (t % 12)

            for item_idx, item in enumerate(CATALOG):
                if len(rows) >= target_count:
                    break

                var_noise = item.get("volatility", 0.02) * math.sin(t * 0.7 + item_idx * 1.3)
                unit_price = round(item["base_price"] * inflation_factor * (1.0 + var_noise), 2)

                qty = item.get("base_qty", 1)
                unit = item["unit"]
                discount = item.get("special_discount", 0.0)
                fee = item.get("fee", 0.0)
                tax = item.get("tax", 0.0)
                deposit = item.get("deposit", 0.0)

                # Periodic promotional discount
                if item.get("has_discount") and (t + item_idx) % 4 == 0:
                    discount = round(unit_price * 0.15, 2)

                paid_total = -round(qty * unit_price - discount - fee - tax - deposit, 2)

                day = min(28, 2 + ((item_idx * 3 + t) % 26))
                receipt_date = f"{month_str}-{day:02d}"
                receipt_id = f"REC-{month_str.replace('-', '')}-{row_id_counter:05d}"

                rows.append({
                    "month": month_str,
                    "receipt_id": receipt_id,
                    "receipt_date": receipt_date,
                    "merchant": item["merchant"],
                    "item_raw": item["item_raw"],
                    "item_normalized": item["item_normalized"],
                    "category": item["category"],
                    "quantity": str(qty),
                    "unit": unit,
                    "shelf_unit_price": f"{unit_price:.2f}",
                    "currency": "MXN",
                    "discount": f"{discount:.2f}" if discount else "0",
                    "fee": f"{fee:.2f}" if fee else "0",
                    "tax": f"{tax:.2f}" if tax else "0",
                    "deposit": f"{deposit:.2f}" if deposit else "0",
                    "paid_total": f"{paid_total:.2f}",
                    "event_type": item["event_type"],
                    "source_file": "example_month.csv",
                    "notes": f"Synthetic line item {item_idx + 1}",
                })
                row_id_counter += 1

            # Periodic non-purchase events
            if m_num in (6, 12) and len(rows) < target_count:
                rows.append({
                    "month": month_str,
                    "receipt_id": f"REC-{month_str.replace('-', '')}-{row_id_counter:05d}",
                    "receipt_date": f"{month_str}-24",
                    "merchant": "Familia",
                    "item_raw": "Apoyo Familiar",
                    "item_normalized": "family financial support",
                    "category": "Transfers and gifts",
                    "quantity": "1",
                    "unit": "piece",
                    "shelf_unit_price": "3000.00",
                    "currency": "MXN",
                    "discount": "0",
                    "fee": "0",
                    "tax": "0",
                    "deposit": "0",
                    "paid_total": "3000.00",
                    "event_type": "income",
                    "source_file": "example_month.csv",
                    "notes": "Semi-annual family support gift",
                })
                row_id_counter += 1

    return rows[:target_count]


def main():
    target_path = Path(__file__).resolve().parents[1] / "data" / "example_month.csv"
    target_path.parent.mkdir(parents=True, exist_ok=True)
    rows = generate_rows(10000)

    headers = [
        "month", "receipt_id", "receipt_date", "merchant", "item_raw",
        "item_normalized", "category", "quantity", "unit", "shelf_unit_price",
        "currency", "discount", "fee", "tax", "deposit", "paid_total",
        "event_type", "source_file", "notes",
    ]
    with target_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"Successfully wrote {len(rows)} rows to {target_path}")


if __name__ == "__main__":
    main()
