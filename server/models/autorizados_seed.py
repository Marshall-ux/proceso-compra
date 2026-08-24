"""Listado de autorizados segun los PDFs 'AUTORIZACION GENERAL ORDENES DE COMPRA - MONTOS'
(Rev. Sep. 2025). monto_autorizado en None significa SIN LIMITE.

lista: a que planilla pertenece cada persona. Determina para que marcas puede autorizar
(ver services/marcas.py).
"""

AUTORIZADOS = [
    # ---------------------------- NISSAN ------------------------------------
    {
        'nombre': 'Marcos Scerra',
        'cargo': 'Jefe de Ventas NISSAN',
        'lista': 'nissan',
        'monto_autorizado': 3500000.00,
        'conceptos': 'Todo lo relativo a su operacion comercial a cargo, descuentos, accesorios, '
                     'gastos de MKT y todo lo relacionado al ejercicio de la marca.',
    },
    {
        'nombre': 'Ignacio Parolin',
        'cargo': 'Ases. De Repuestos NISSAN',
        'lista': 'nissan',
        'monto_autorizado': 3500000.00,
        'conceptos': 'En lo que respecta al desarrollo del negocio de repuestos - servicios y '
                     'acarreos, puestos, etc.',
    },
    {
        'nombre': 'Ma. Laura Henning',
        'cargo': 'Resp. Compras Adm. XINOXIA',
        'lista': 'nissan',
        'monto_autorizado': 500000.00,
        'conceptos': 'Todo lo relativo a articulos, elementos y utiles de adm y finanzas para adm.',
    },
    {
        'nombre': 'Juan Peralta',
        'cargo': 'Asesor de repuestos NISSAN',
        'lista': 'nissan',
        'monto_autorizado': 2500000.00,
        'conceptos': 'Todo lo relativo a compras de repuestos NISSAN.',
    },
    {
        'nombre': 'Ignacio Aguilar',
        'cargo': 'Ases. De Repuestos NISSAN',
        'lista': 'nissan',
        'monto_autorizado': 2000000.00,
        'conceptos': 'Reemplaza a IGNACIO PAROLIN cuando este se encuentre de licencia.',
    },
    {
        'nombre': 'Walter Palomino',
        'cargo': 'Ases. De Repuestos NISSAN',
        'lista': 'nissan',
        'monto_autorizado': 1500000.00,
        'conceptos': 'Reemplaza a JUAN PERALTA cuando ese se encuentre de licencia.',
    },

    # ------------------------- JEEP / CHRYSLER (FCA) ------------------------
    {
        'nombre': 'Marcelo Calvete',
        'cargo': 'Jefe de ventas CHRYSLER',
        'lista': 'jeep',
        'monto_autorizado': 3500000.00,
        'conceptos': 'Todo lo relativo a su operacion comercial a cargo, descuentos, accesorios, '
                     'gastos de MKT, viaticos, capacitaciones y todo lo relativo al ejercicio '
                     'comercial de la marca.',
    },
    {
        'nombre': 'Laura Discipio',
        'cargo': 'Resp. En adm CHRYSLER',
        'lista': 'jeep',
        'monto_autorizado': 500000.00,
        'conceptos': 'Todo lo relativo a articulos y utiles de adm. Y finanzas para adm.',
    },
    {
        'nombre': 'Ignacio Siffredi',
        'cargo': 'Encargado de PostVenta CHRYSLER',
        'lista': 'jeep',
        'monto_autorizado': 2500000.00,
        'conceptos': 'Todo lo relativo a servicios y repuestos de taller Chrysler.',
    },
    {
        'nombre': 'Lisandro Caseres',
        'cargo': 'Jefe de PostVenta General',
        'lista': 'jeep',
        'monto_autorizado': 3500000.00,
        'conceptos': 'Viaticos, capacitaciones y todo lo relativo a servicios de taller Chrysler.',
    },
    {
        'nombre': 'Andres Fernandez',
        'cargo': 'Jefe de PostVenta CHRYSLER',
        'lista': 'jeep',
        'monto_autorizado': 2500000.00,
        'conceptos': 'En lo que respecta al desarrollo del negocio del Servicio de Post Venta - '
                     'Taller y Repuestos Chrysler. Ej: Repuestos y servicios de referencia.',
    },

    # ------------------------------- KIA ------------------------------------
    {
        'nombre': 'Bruno Otero',
        'cargo': 'Asesor de Repuestos KIA',
        'lista': 'kia',
        'monto_autorizado': 2500000.00,
        'conceptos': 'Repuestos marca Kia / Suzuki - Post Venta.',
    },
    {
        'nombre': 'Luciano Romero',
        'cargo': 'Asesor de taller y servicios KIA',
        'lista': 'kia',
        'monto_autorizado': 2500000.00,
        'conceptos': 'Todo lo relativo a servicios y materiales para taller Kia. Tambien lo '
                     'relativo a ropa de trabajo y herramientas y materiales para taller.',
    },
    {
        'nombre': 'Mauricio Colombera',
        'cargo': 'Jefe de Ventas',
        'lista': 'kia',
        'monto_autorizado': 1000000.00,
        'conceptos': 'Repuestos, usados y varios comerciales de concesionaria KIA.',
    },
    {
        'nombre': 'Diego Gobetto',
        'cargo': 'Jefe de Post Venta KIA',
        'lista': 'kia',
        'monto_autorizado': 2500000.00,
        'conceptos': 'Todo lo relativo a servicios de la marca Kia y Suzuki. Ej: Serv de 3ros, '
                     'arreglos de chaperia, etc. Tambien lo relativo a ropa de trabajo, '
                     'herramientas y materiales para taller.',
    },
    {
        'nombre': 'Ignacio Vazquez',
        'cargo': 'DIRECTOR Gerente de marca KIA',
        'lista': 'kia',
        'monto_autorizado': None,  # SIN LIMITE
        'conceptos': 'Todo lo relativo a la marca Kia (Servicios y Post venta) y demas marcas, '
                     'en lo referente de gestion comercial.',
    },

    # ---------------------------- MULTIMARCA --------------------------------
    {
        'nombre': 'Raul Garcia',
        'cargo': 'DIRECTOR',
        'lista': 'multimarca',
        'monto_autorizado': None,  # SIN LIMITE
        'conceptos': 'Todo lo relativo a la gestion de calidad y medio ambiente y servicios de '
                     'post venta y repuestos multimarca. Ej: repuestos de post venta, sistema '
                     'desarrollo, nuevas plataformas, contrataciones de serv. etc.',
    },
    {
        'nombre': 'Cecilia Giorgetti',
        'cargo': 'Resp. Contabilidad e impuestos',
        'lista': 'multimarca',
        'monto_autorizado': 3000000.00,
        'conceptos': 'Todo lo relativo a articulos, elementos y utiles, compras de formularios '
                     'Acara, solicitud de facturas, recibos, Contratacion de servicios, viaticos, '
                     'Ases. Contables, articulos de almacen y otros utiles de adm y finanzas.',
    },
    {
        'nombre': 'Silvina Torres',
        'cargo': 'Resp. Operativa',
        'lista': 'multimarca',
        'monto_autorizado': 3000000.00,
        'conceptos': 'Todo lo relativo a articulos, elementos y utiles, compra de formularios '
                     'ACARA, solicitud de facturas, recibos, viatico, contratacion de servicios '
                     'laborales, articulos de almacen y otros utiles de Adm y Fzas.',
    },
    # Martin Depetris (Gerente Vtas FUNES) - baja: ya no trabaja en la empresa (ago-2026).
    # Se saca del roster; si su fila existe en la base, queda inactiva (no se borra, para
    # conservar el historial de lo que haya firmado).
    {
        'nombre': 'Luciano Falletti',
        'cargo': 'Gerente Vtas CDG',
        'lista': 'multimarca',
        'monto_autorizado': 3500000.00,
        'conceptos': 'Todo lo relativo a insumos para sucursal, lavadero, jardineria, '
                     'combustible, servicios y repuestos, etc.',
    },
    {
        'nombre': 'Juan Azzolini',
        'cargo': 'DIRECTOR',
        'lista': 'multimarca',
        'monto_autorizado': None,  # SIN LIMITE
        'conceptos': 'Todo lo relativo al area comercial y finanzas, puede autorizar servicios, '
                     'comerciales y de taller de excepcion.',
    },
    {
        'nombre': 'Sebastian Vazquez',
        'cargo': 'DIRECTOR',
        'lista': 'multimarca',
        'monto_autorizado': None,  # SIN LIMITE
        'conceptos': 'TODOS LOS CONCEPTOS',
    },
    {
        'nombre': 'Ezequiel Vazquez',
        'cargo': 'DIRECTOR',
        'lista': 'multimarca',
        'monto_autorizado': None,  # SIN LIMITE
        'conceptos': 'TODOS LOS CONCEPTOS',
    },
    {
        'nombre': 'Jorgelina Vazquez',
        'cargo': 'DIRECTOR',
        'lista': 'multimarca',
        'monto_autorizado': None,  # SIN LIMITE
        'conceptos': 'TODOS LOS CONCEPTOS',
    },

    # ---------------------------- MARKETING ---------------------------------
    {
        'nombre': 'Virginia Lottero',
        'cargo': 'Gerente de MKT',
        'lista': 'multimarca',
        'monto_autorizado': 8000000.00,  # el mayor de sus topes por concepto
        'conceptos': 'Marketing. Topes por concepto: Fee agencia de publicidad / Tep (Tadinac) / '
                     'diseños y anuncios hasta $2.000.000; Selección Digital SA / fondeo MKT digital '
                     'hasta $8.000.000; Merchandising sucursales (regalos 0km, tablas, parasoles) '
                     'hasta $8.000.000; Materiales para eventos (flagbanner, sombrillas, gazebos) '
                     'hasta $2.000.000; Material POP (tarjetas, folletería, carteles) hasta '
                     '$1.000.000; Coberturas audiovisuales (radio, influencer) hasta $500.000. '
                     'Requiere Director para: campañas especiales (aniversarios, mundial, etc.), '
                     'viajes/hospedajes/pasajes, eventos > $3.000.000 y publicidad > $1.000.000.',
    },

    # -------------------------- SANTA FE (Honda / BYD / KIA) -----------------
    {
        'nombre': 'German R. Bru',
        'cargo': 'Gerente de Ventas Honda (Santa Fe)',
        'lista': 'honda',
        'monto_autorizado': 5000000.00,
        'conceptos': 'Todo lo relativo a su operacion comercial a cargo, descuentos, accesorios, '
                     'gastos de MKT y todo lo relativo al ejercicio de la marca.',
    },
    {
        'nombre': 'Dora Ubiergo',
        'cargo': 'Gerente de ventas BYD (Santa Fe)',
        'lista': 'byd',
        'monto_autorizado': 5000000.00,
        'conceptos': 'Todo lo relativo a su operacion comercial a cargo, descuentos, accesorios, '
                     'gastos de MKT y todo lo relativo al ejercicio comercial de la marca.',
    },
    {
        'nombre': 'Luciana Harik',
        'cargo': 'Asesora comercial (Santa Fe)',
        'lista': 'byd',
        'monto_autorizado': 1000000.00,
        'conceptos': 'Todo lo relativo a compras de articulos de libreria, higiene y almacen, '
                     'gestion de calidad y medio ambiente.',
    },
    {
        'nombre': 'Cesar Bourquin',
        'cargo': 'Asesor de taller y servicios KIA (Santa Fe)',
        'lista': 'kia',
        'monto_autorizado': 2500000.00,
        'conceptos': 'Todo lo relativo a post venta de las distintas razones sociales (Neostar, '
                     'Hikari, Alco Rosario, Daseos, Xinoxia) de Santa Fe.',
    },
    {
        'nombre': 'Barbara Ayala',
        'cargo': 'Responsable Administracion Santa Fe',
        'lista': 'multimarca',
        'monto_autorizado': 2500000.00,
        'conceptos': 'Todo lo relativo a articulos, elementos y utiles, compra de formularios ACARA, '
                     'solicitud de facturas, recibos y otros utiles de Adm y Fzas. (Santa Fe)',
    },
    {
        'nombre': 'Marisol Gonzalez',
        'cargo': 'Control Interno Honda (Santa Fe)',
        'lista': 'multimarca',
        'monto_autorizado': 2500000.00,
        'conceptos': 'Todo lo relativo a articulos, elementos y utiles, compra de formularios ACARA, '
                     'solicitud de facturas, recibos y otros utiles de Adm y Fzas. (Santa Fe)',
    },
    {
        'nombre': 'Roman Cabrera',
        'cargo': 'Gerente de post venta General (Santa Fe)',
        'lista': 'multimarca',
        'monto_autorizado': 5000000.00,
        'conceptos': 'Todo lo relativo a post venta de las distintas razones sociales (Neostar, '
                     'Hikari, Alco Rosario, Daseos, Xinoxia) de Santa Fe. Tope para BYD: $3.500.000.',
    },
    {
        'nombre': 'Sergio Vazquez',
        'cargo': 'DIRECTOR (Santa Fe)',
        'lista': 'multimarca',
        'monto_autorizado': None,  # SIN LIMITE
        'conceptos': 'TODOS LOS CONCEPTOS',
    },
]
