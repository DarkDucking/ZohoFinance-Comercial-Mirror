import json
import requests
import google.auth
from google.auth.transport.requests import Request
from google.oauth2.service_account import Credentials
import gspread
from gspread_dataframe import set_with_dataframe
import datetime as dt
import time
import pandas as pd
import pypyodbc as odbc # pip install pypyodbc

# Credenciales para conectarse con Comercial FOM
DRIVER_NAME = 'Sql Server'
SERVER_NAME = '172.16.100.14\COMERCIAL2019'
DATABASE_NAME = 'adFIBER_OPTIC_NETWORK'
DATABASE_NAME_WO = 'adWO_MAN_COM'
UID_NAME = 'sa'
PWD_NAME = 'Chesse2389'

# Configuración de las credenciales de Google Sheets
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SERVICE_ACCOUNT_FILE = 'prueba-api-python.json'  # Ruta al archivo de credenciales JSON

# Configuración de las credenciales de Zoho Inventory
ZOHO_CLIENT_ID = '1000.FIUHTDW4J4UMO8USPVVNSJDJL8S4AQ'
ZOHO_CLIENT_SECRET = '8ad548c60b1bb613f0c09dcb953322fcb5675cbd2c'
ZOHO_REFRESH_TOKEN = '1000.8b3eb4081b97823a6ae1b965c6229323.2d198eab2170def63d01a17c3fcd7b32'
ZOHO_ORG_ID = '856825010'

# ID de la hoja de 1WjI-RDgwnHTpVgz3nD7lXV621a-de4pHD1oE6LkRFzs cálculo
SPREADSHEET_ID = '1WjI-RDgwnHTpVgz3nD7lXV621a-de4pHD1oE6LkRFzs'

# Autenticar y autorizar acceso a Google Sheets
creds = None
creds = Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)
client = gspread.authorize(creds)

# Abrir la hoja de cálculo usando su ID
spreadsheet = client.open_by_key(SPREADSHEET_ID)

# Seleccionar la primera hoja (worksheet) de la hoja de cálculo
sheet = spreadsheet.worksheet("Insercion")
sheet_bd = spreadsheet.worksheet("BD")
sheet_comercial = spreadsheet.worksheet("Comercial")

# Funcion para hacer la conexion con la BD
def connection_string(driver_name, server_name, database_name, uid_name, pwd_name):
    # uid=<username>;
    # pwd=<password>;
    conn_string = f"""
        DRIVER={{{driver_name}}};
        SERVER={server_name};
        DATABASE={database_name};
        UID={uid_name};
        PWD={pwd_name};        
    """
    
    return conn_string


# SQL de inserion a Google sheets del inventario en Comercial FONCS
def sql_query_foncs():
    # Se intenta la conexion con la base de datos
    try:
        conn = odbc.connect(connection_string(DRIVER_NAME,SERVER_NAME,DATABASE_NAME,UID_NAME,PWD_NAME))
        print('Connection Created')
    except odbc.DatabaseError as e:
        print('Database Error:')
        print(str(e.value[1]))
    except odbc.Error as e:
        print('Connection Error:')
        print(str(e.value[1]))
    else: 
        # Declaracion de query
        sql_query = """
        SELECT      
            CASE
                WHEN TABLA1.CCODIGOALMACEN = 'CEDISLTX' THEN '5371960000000121010'
            END AS [Almacen],  
            TABLA1.CCODIGOPRODUCTO AS [SKU],
            TABLA1.CNOMBREPRODUCTO AS [Name],
            U.CABREVIATURA AS [Unit],
            TABLA1.CPRECIO2 AS [Price],
            TABLA1.EXISTENCIA AS [Stock],       
            TABLA1.LOTE AS [Batch],     
            TABLA1.CNUMEROSERIE AS [Serial],
            TABLA1.CDESCRIPCIONPRODUCTO AS [Descripcion],     
            AJUSTE = 0

        FROM (     
            -- Primera subconsulta
            SELECT           
                dbo.admProductos.CCODIGOPRODUCTO,       
                dbo.admProductos.CNOMBREPRODUCTO,        
                CAST(dbo.admProductos.CDESCRIPCIONPRODUCTO AS VARCHAR(MAX)) AS CDESCRIPCIONPRODUCTO,      
                dbo.admProductos.CIDUNIDADBASE,
                dbo.admProductos.CPRECIO2,
                dbo.admAlmacenes.CCODIGOALMACEN,              
                dbo.admNumerosSerie.CPEDIMENTO,       
                '' AS [LOTE],        
                dbo.admNumerosSerie.CNUMEROSERIE,
                1 AS EXISTENCIA
            FROM dbo.admProductos      
            FULL OUTER JOIN dbo.admNumerosSerie 
                ON dbo.admProductos.CIDPRODUCTO = dbo.admNumerosSerie.CIDPRODUCTO
            FULL OUTER JOIN dbo.admAlmacenes 
                ON dbo.admNumerosSerie.CIDALMACEN = dbo.admAlmacenes.CIDALMACEN 
            WHERE (dbo.admProductos.CTIPOPRODUCTO = 1) AND (dbo.admNumerosSerie.CESTADO < 3)   

            UNION     

            -- Segunda subconsulta
            SELECT        
                dbo.admProductos.CCODIGOPRODUCTO,      
                dbo.admProductos.CNOMBREPRODUCTO,      
                CAST(dbo.admProductos.CDESCRIPCIONPRODUCTO AS VARCHAR(MAX)) AS CDESCRIPCIONPRODUCTO,   
                dbo.admProductos.CIDUNIDADBASE,    
                dbo.admProductos.CPRECIO2, 
                dbo.admAlmacenes.CCODIGOALMACEN,               
                dbo.admCapasProducto.CPEDIMENTO,      
                dbo.admCapasProducto.CNUMEROLOTE,      
                '' AS [SERIE],     
                SUM(ISNULL(dbo.admCapasProducto.CEXISTENCIA, 0)) AS EXISTENCIA
            FROM dbo.admCapasProducto    
            FULL OUTER JOIN dbo.admAlmacenes 
                ON dbo.admCapasProducto.CIDALMACEN = dbo.admAlmacenes.CIDALMACEN   
            FULL OUTER JOIN dbo.admProductos 
                ON dbo.admCapasProducto.CIDPRODUCTO = dbo.admProductos.CIDPRODUCTO 
            WHERE (dbo.admProductos.CTIPOPRODUCTO = 1) 
                AND (dbo.admProductos.CSTATUSPRODUCTO = 1) 
                AND (dbo.admCapasProducto.CEXISTENCIA > 0)  
            GROUP BY        
                dbo.admProductos.CCODIGOPRODUCTO,       
                dbo.admProductos.CNOMBREPRODUCTO,      
                dbo.admProductos.CIDUNIDADBASE,          
                dbo.admAlmacenes.CCODIGOALMACEN,                 
                dbo.admCapasProducto.CPEDIMENTO,        
                dbo.admCapasProducto.CNUMEROLOTE, 
                dbo.admProductos.CPRECIO2,
                CAST(dbo.admProductos.CDESCRIPCIONPRODUCTO AS VARCHAR(MAX))

            UNION      

            SELECT          
                dbo.admProductos.CCODIGOPRODUCTO,    
                dbo.admProductos.CNOMBREPRODUCTO,      
                CAST(dbo.admProductos.CDESCRIPCIONPRODUCTO AS VARCHAR(MAX)) AS CDESCRIPCIONPRODUCTO,    
                dbo.admProductos.CIDUNIDADBASE,
                dbo.admProductos.CPRECIO2,
                dbo.admAlmacenes.CCODIGOALMACEN,                   
                '' AS PEDIMENTO,           
                '' AS LOTE,             
                '' AS [SERIE],
                ROUND(ISNULL((SELECT SUM(CASE WHEN cAfectaExistencia = 1 THEN cUnidades ELSE 0 END)          
                            - SUM(CASE WHEN cAfectaExistencia = 2 THEN cUnidades ELSE 0 END) AS Expr1     
                            FROM dbo.admMovimientos                      
                            LEFT OUTER JOIN dbo.admProductos AS p 
                            ON dbo.admMovimientos.CIDPRODUCTO = p.CIDPRODUCTO 
                            WHERE (dbo.admMovimientos.CIDALMACEN = dbo.admAlmacenes.CIDALMACEN)              
                            AND (dbo.admMovimientos.CIDPRODUCTO = dbo.admProductos.CIDPRODUCTO)            
                            AND (dbo.admMovimientos.CFECHA < GETDATE())                        
                            AND (dbo.admMovimientos.CAFECTADOINVENTARIO <> 0)), 0.0), 5, 0) AS EXISTENCIA
            FROM dbo.admProductos          
            CROSS JOIN dbo.admAlmacenes          
            WHERE (dbo.admProductos.CSTATUSPRODUCTO = 1)         
                AND (dbo.admProductos.CTIPOPRODUCTO = 1)      
                AND (dbo.admProductos.CCONTROLEXISTENCIA < 4)     
        ) AS TABLA1 
        INNER JOIN dbo.admUnidadesMedidaPeso AS U 
            ON U.CIDUNIDAD = TABLA1.CIDUNIDADBASE 
        WHERE (TABLA1.CCODIGOALMACEN LIKE 'CEDISLTX')
            AND TABLA1.CPRECIO2 <> 0
            AND TABLA1.CCODIGOPRODUCTO NOT LIKE 'Z%'
        """
        # Se ejecuta la query
        cursor = conn.cursor()
        cursor.execute(sql_query)

        recordset = cursor.fetchall()
        # Se sacan las columnas
        columns = ["Almacen", "SKU", "Name", "Unit", "Price", "Stock", "Batch", "Serial", "Descripcion" ,"Ajuste"]
        # Se hace un dataframe del query
        df = pd.DataFrame(recordset, columns=columns)
        # Limpiamos el sheet y ponemos la info
        sheet_comercial.clear()
        set_with_dataframe(sheet_comercial, df)


# SQL de inserion a Google sheets del inventario en Comercial FONCS
def sql_query_wo():
    # Se intenta la conexion con la base de datos
    try:
        conn = odbc.connect(connection_string(DRIVER_NAME,SERVER_NAME,DATABASE_NAME_WO,UID_NAME,PWD_NAME))
        print('Connection Created')
    except odbc.DatabaseError as e:
        print('Database Error:')
        print(str(e.value[1]))
    except odbc.Error as e:
        print('Connection Error:')
        print(str(e.value[1]))
    else: 
        # Declaracion de query
        sql_query = """
        SELECT      
            CASE
                WHEN TABLA1.CCODIGOALMACEN = '999' THEN '5371960000000121036'
            END AS [Almacen],   
            TABLA1.CCODIGOPRODUCTO AS [SKU],
            TABLA1.CNOMBREPRODUCTO AS [Name],
            U.CABREVIATURA AS [Unit],
            TABLA1.CPRECIO2 AS [Price],
            TABLA1.EXISTENCIA AS [Stock],       
            TABLA1.LOTE AS [Batch],     
            TABLA1.CNUMEROSERIE AS [Serial],     
            TABLA1.CCLAVESAT AS [SAT code],
            U.CCLAVESAT AS [SAT unit],
            AJUSTE = 0

            FROM (     
                -- Primera subconsulta
                SELECT           
                    dbo.admProductos.CCODIGOPRODUCTO,       
                    dbo.admProductos.CNOMBREPRODUCTO,        
                    CAST(dbo.admProductos.CDESCRIPCIONPRODUCTO AS VARCHAR(MAX)) AS CDESCRIPCIONPRODUCTO,      
                    dbo.admProductos.CIDUNIDADBASE,
                    dbo.admProductos.CPRECIO2,
                    dbo.admAlmacenes.CCODIGOALMACEN,              
                    dbo.admNumerosSerie.CPEDIMENTO,       
                    '' AS [LOTE],        
                    dbo.admNumerosSerie.CNUMEROSERIE,
                    1 AS EXISTENCIA,  
                    dbo.admProductos.CCLAVESAT
                FROM dbo.admProductos      
                FULL OUTER JOIN dbo.admNumerosSerie 
                    ON dbo.admProductos.CIDPRODUCTO = dbo.admNumerosSerie.CIDPRODUCTO
                FULL OUTER JOIN dbo.admAlmacenes 
                    ON dbo.admNumerosSerie.CIDALMACEN = dbo.admAlmacenes.CIDALMACEN 
                WHERE (dbo.admProductos.CTIPOPRODUCTO = 1) AND (dbo.admNumerosSerie.CESTADO < 3)   

                UNION     

                -- Segunda subconsulta
                SELECT        
                    dbo.admProductos.CCODIGOPRODUCTO,      
                    dbo.admProductos.CNOMBREPRODUCTO,      
                    CAST(dbo.admProductos.CDESCRIPCIONPRODUCTO AS VARCHAR(MAX)) AS CDESCRIPCIONPRODUCTO,   
                    dbo.admProductos.CIDUNIDADBASE,    
                    dbo.admProductos.CPRECIO2, 
                    dbo.admAlmacenes.CCODIGOALMACEN,               
                    dbo.admCapasProducto.CPEDIMENTO,      
                    dbo.admCapasProducto.CNUMEROLOTE,      
                    '' AS [SERIE],     
                    SUM(ISNULL(dbo.admCapasProducto.CEXISTENCIA, 0)) AS EXISTENCIA, 
                    dbo.admProductos.CCLAVESAT
                FROM dbo.admCapasProducto    
                FULL OUTER JOIN dbo.admAlmacenes 
                    ON dbo.admCapasProducto.CIDALMACEN = dbo.admAlmacenes.CIDALMACEN   
                FULL OUTER JOIN dbo.admProductos 
                    ON dbo.admCapasProducto.CIDPRODUCTO = dbo.admProductos.CIDPRODUCTO 
                WHERE (dbo.admProductos.CTIPOPRODUCTO = 1) 
                    AND (dbo.admProductos.CSTATUSPRODUCTO = 1) 
                    AND (dbo.admCapasProducto.CEXISTENCIA > 0)  
                GROUP BY        
                    dbo.admProductos.CCODIGOPRODUCTO,       
                    dbo.admProductos.CNOMBREPRODUCTO,      
                    dbo.admProductos.CIDUNIDADBASE,          
                    dbo.admAlmacenes.CCODIGOALMACEN,                 
                    dbo.admCapasProducto.CPEDIMENTO,        
                    dbo.admCapasProducto.CNUMEROLOTE, 
                    dbo.admProductos.CPRECIO2,
                    CAST(dbo.admProductos.CDESCRIPCIONPRODUCTO AS VARCHAR(MAX)),
                    dbo.admProductos.CCLAVESAT

                UNION      

                SELECT          
                    dbo.admProductos.CCODIGOPRODUCTO,    
                    dbo.admProductos.CNOMBREPRODUCTO,      
                    CAST(dbo.admProductos.CDESCRIPCIONPRODUCTO AS VARCHAR(MAX)) AS CDESCRIPCIONPRODUCTO,    
                    dbo.admProductos.CIDUNIDADBASE,
                    dbo.admProductos.CPRECIO2,
                    dbo.admAlmacenes.CCODIGOALMACEN,                   
                    '' AS PEDIMENTO,           
                    '' AS LOTE,             
                    '' AS [SERIE],
                    ROUND(ISNULL((SELECT SUM(CASE WHEN cAfectaExistencia = 1 THEN cUnidades ELSE 0 END)          
                                - SUM(CASE WHEN cAfectaExistencia = 2 THEN cUnidades ELSE 0 END) AS Expr1     
                                FROM dbo.admMovimientos                      
                                LEFT OUTER JOIN dbo.admProductos AS p 
                                ON dbo.admMovimientos.CIDPRODUCTO = p.CIDPRODUCTO 
                                WHERE (dbo.admMovimientos.CIDALMACEN = dbo.admAlmacenes.CIDALMACEN)              
                                AND (dbo.admMovimientos.CIDPRODUCTO = dbo.admProductos.CIDPRODUCTO)            
                                AND (dbo.admMovimientos.CFECHA < GETDATE())                        
                                AND (dbo.admMovimientos.CAFECTADOINVENTARIO <> 0)), 0.0), 5, 0) AS EXISTENCIA,
                    dbo.admProductos.CCLAVESAT
                FROM dbo.admProductos          
                CROSS JOIN dbo.admAlmacenes          
                WHERE (dbo.admProductos.CSTATUSPRODUCTO = 1)         
                    AND (dbo.admProductos.CTIPOPRODUCTO = 1)      
                    AND (dbo.admProductos.CCONTROLEXISTENCIA < 4)     
            ) AS TABLA1 
            INNER JOIN dbo.admUnidadesMedidaPeso AS U 
                ON U.CIDUNIDAD = TABLA1.CIDUNIDADBASE 
        WHERE
        TABLA1.EXISTENCIA > 0
        AND TABLA1.CCODIGOALMACEN LIKE '999'
        """
        # Se ejecuta la query
        cursor = conn.cursor()
        cursor.execute(sql_query)

        recordset = cursor.fetchall()
        # Se sacan las columnas
        columns = ["Almacen", "SKU", "Name", "Unit", "Price", "Stock", "Batch", "Serial", "Ajuste"]
        # Se hace un dataframe del query
        df = pd.DataFrame(recordset, columns=columns)
        # Agregamos  la info al sheet de comercial
        set_with_dataframe(sheet_comercial, df)


# Funcion que hace una query de los diferentes precios de los productos
def sql_query_priceList():
    # Se intenta la conexion con la base de datos
    try:
        conn = odbc.connect(connection_string(DRIVER_NAME,SERVER_NAME,DATABASE_NAME,UID_NAME,PWD_NAME))
        print('Connection Created')
    except odbc.DatabaseError as e:
        print('Database Error:')
        print(str(e.value[1]))
    except odbc.Error as e:
        print('Connection Error:')
        print(str(e.value[1]))
    else: 
        # Declaracion de query
        sql_query = """
            Select CCODIGOPRODUCTO,
            CNOMBREPRODUCTO,
            CPRECIO2,
            CPRECIO5,
            CPRECIO8
            from admProductos 
            WHERE CPRECIO2 <> 0
            AND CCODIGOPRODUCTO NOT LIKE 'Z%';
            """
        
        # Se ejecuta la query
        cursor = conn.cursor()
        cursor.execute(sql_query)

        recordset = cursor.fetchall()
        # Se sacan las columnas
        columns = ["SKU", "Name", "Price 2", "Price 5", "Price 8"]
        # Se hace un dataframe del query
        query_df = pd.DataFrame(recordset, columns=columns)

        # Extraer los datos de la hoja BD
        bd_data = sheet_bd.get_all_records()
        df_bd = pd.DataFrame(bd_data).astype({"Item_Id": "string","Batch_Id": "string","Almacen": "string",})

        # Crear nuevo df para la insercion de listas de precios, lo hacemos con un ciclo de 3 vueltas para la lista 2,5 y 7
        price_list_df =  pd.DataFrame(columns=query_df.columns)

        # Iterar en cada linea de los productos, buscar coincidencias y agregarlos o actualizar la lista de precios
        for index, row in df_bd.iterrows():
            # Buscamos que coincidan los SKU
            if row["SKU"] in query_df["SKU"].values:
                # Encontrar las líneas que coinciden
                matching_row = query_df[query_df["SKU"] == row["SKU"]].iloc[0]
                # Convertir a DataFrame para asegurar estructura correcta
                matching_row_df = pd.DataFrame([matching_row.to_dict()])
                # Agregar el id del Item
                matching_row_df["Item_Id"] = row["Item_Id"]
                # Concatenar el nuevo DataFrame
                price_list_df = pd.concat([price_list_df, matching_row_df], ignore_index=True)

        price_list_df = price_list_df.drop_duplicates("SKU")
        price_list_df = price_list_df.reset_index(drop=True)

        update_price_list(5371960000000175013, price_list_df, "Price 2", "Price List 2", access_token)
        update_price_list(5371960000000175033, price_list_df, "Price 5", "Price List 5", access_token)
        update_price_list(5371960000000175039, price_list_df, "Price 8", "Price List 8", access_token)


# Función para obtener el token de acceso de Zoho
def get_zoho_access_token():
    url = 'https://accounts.zoho.com/oauth/v2/token'
    params = {
        'refresh_token': ZOHO_REFRESH_TOKEN,
        'client_id': ZOHO_CLIENT_ID,
        'client_secret': ZOHO_CLIENT_SECRET,
        'grant_type': 'refresh_token'
    }
    response = requests.post(url, params=params)
    response_data = response.json()
    return response_data['access_token']


# Función para crear un nuevo artículo en Zoho Inventory
def create_item_in_zoho(item_data, access_token):
    url = f'https://www.zohoapis.com/inventory/v1/items?organization_id={ZOHO_ORG_ID}'
    headers = {
        'Authorization': f'Zoho-oauthtoken {access_token}',
        'Content-Type': 'application/json'
    }
    try:
        response = requests.post(url, headers=headers, json=item_data)
        response_data = response.json()

        # Verificar si hubo un error en la respuesta
        if response.status_code != 201:
            #Existe el item
            if response.status_code == 400:
                return "Existe"
            else:
                # Imprimir mensaje de error si el estado no es el esperado
                print("Error:", response_data.get('message', 'Unknown error'))
        else:
            return response_data  # Devuelve la respuesta en caso de éxito

    except requests.exceptions.RequestException as e:
        # Captura errores de red y otros problemas en la solicitud
        print("Request failed:", e)


# Función para crear un Ajuste de Inventario para modificar, agregar y quitar batch
def inventory_adjustement(item_data, access_token):
    url = f'https://www.zohoapis.com/inventory/v1/inventoryadjustments?organization_id={ZOHO_ORG_ID}'
    headers = {
        'Authorization': f'Zoho-oauthtoken {access_token}',
        'Content-Type': 'application/json'
    }
    try:
        response = requests.post(url, headers=headers, json=item_data)
        response_data = response.json()

        # Verificar si hubo un error en la respuesta
        if response.status_code != 201:
            if response_data.get('code') == 2303:
                print("Batch Existente")
            # Imprimir mensaje de error si el estado no es el esperado
            print("Error:", response_data.get('message', 'Unknown error'))
        else:
            return response_data  # Devuelve la respuesta en caso de éxito

    except requests.exceptions.RequestException as e:
        # Captura errores de red y otros problemas en la solicitud
        print("Request failed:", e)


#Funcion para actualizar un artículo en Zoho Inventory
def update_item(item_id, item_data, access_token):
    url = f'https://www.zohoapis.com/inventory/v1/items/{item_id}?organization_id={ZOHO_ORG_ID}'
    headers = {
        'Authorization': f'Zoho-oauthtoken {access_token}',
        'Content-Type': 'application/json',
    }
    response = requests.put(url, headers=headers, json=item_data)
    return response.json()


# Checa si el item Existe
def itemExist(sku, access_token):
    url = f'https://www.zohoapis.com/inventory/v1/items?organization_id={ZOHO_ORG_ID}'
    headers = {
        'Authorization': f'Zoho-oauthtoken {access_token}',
        'Content-Type': 'application/json'
    }

    page = 1  # Inicializar la paginación
    while True:
        # Agregar el parámetro de paginación
        response = requests.get(f"{url}&page={page}", headers=headers)
        
        # Manejar errores en la solicitud
        if response.status_code != 200:
            print(f"Error al obtener los ítems: {response.status_code} - {response.text}")
            return None
        
        data = response.json()
        items = data.get('items', [])
        
        # Buscar el SKU en los resultados de la página actual
        for item in items:
            if item.get('sku', '') == sku:
                return item.get('item_id')
        
        # Verificar si hay más páginas
        if not data.get('page_context', {}).get('has_more_page', False):
            break  # Salir del bucle si no hay más páginas
        
        # Avanzar a la siguiente página
        page += 1

    # Si no se encuentra el SKU
    print(f"ID no encontrado para SKU {sku}")
    return None


# Actualiza el item en Zoho Inventory
def update_item_inventory(item_data, access_token, item_id):
    url = f'https://www.zohoapis.com/inventory/v1/items/{item_id}?organization_id={ZOHO_ORG_ID}'
    headers = {
        'Authorization': f'Zoho-oauthtoken {access_token}',
        'Content-Type': 'application/json'
    }
    try:
        response = requests.put(url, headers=headers, json=item_data)
        response_data = response.json()

        # Verificar si hubo un error en la respuesta
        if response.status_code != 201:
            # Imprimir mensaje de error si el estado no es el esperado
            print("Error:", response_data.get('message', 'Unknown error'))
        else:
            return response_data  # Devuelve la respuesta en caso de éxito

    except requests.exceptions.RequestException as e:
        # Captura errores de red y otros problemas en la solicitud
        print("Request failed:", e)


# Actualizar las listas de precios
def update_price_list(pricebook_id, dataframe, rate, name, access_token):
    # Creamos la lista de productos de la BD con su pricelist
    items = []
    # Agregamos la info de cada item con el precio especificado
    for index, row in dataframe.iterrows():
        item = {
        "item_id": row["Item_Id"],
        "pricebook_rate": row[rate]
        }
        items.append(item)
    
    # Hacemos el objeto
    item_data = {
        "name": name,
        "currency_id": 5371960000000000097,
        "pricebook_type": "per_item",
        "pricebook_items": items,
        "sales_or_purchase_type": "sales"
    }

    # Hace request Updat PriceList enviando el objeto
    url = f'https://www.zohoapis.com/inventory/v1/pricebooks/{pricebook_id}?organization_id={ZOHO_ORG_ID}'
    headers = {
        'Authorization': f'Zoho-oauthtoken {access_token}',
        'Content-Type': 'application/json'
    }
    try:
        response = requests.put(url, headers=headers, json=item_data)
        response_data = response.json()

        # Verificar si hubo un error en la respuesta
        if response.status_code != 201:
            # Imprimir mensaje de error si el estado no es el esperado
            print("Error:", response_data.get('message', 'Unknown error'))
        else:
            return response_data  # Devuelve la respuesta en caso de éxito

    except requests.exceptions.RequestException as e:
        # Captura errores de red y otros problemas en la solicitud
        print("Request failed:", e)


# Buscar y actualizar los items sin Id
def actualizar_sheets(sku, item_id):
    # Recorrer cada fila en los datos para buscar el SKU
    for index, record in enumerate(data, start=2):  # Comienza en 2 si tienes encabezado
        if record.get("SKU") == sku:
            # Convertir las claves en una lista para obtener el índice de "Item_id"
            column_index = list(record.keys()).index("Item_Id") + 1
            # Actualizar el campo Item_id en la hoja
            sheet.update_cell(index, column_index, item_id)
            time.sleep(5)


# Obtener datos del item
def get_Item(item_id, access_token):
    # Hace request Updat PriceList enviando el objeto
    url = f'https://www.zohoapis.com/inventory/v1/items/{item_id}?organization_id={ZOHO_ORG_ID}'
    headers = {
        'Authorization': f'Zoho-oauthtoken {access_token}',
        'Content-Type': 'application/json'
    }
    try:
        response = requests.get(url, headers=headers)
        response_data = response.json()

        # Verificar si hubo un error en la respuesta
        if response.status_code != 200:
            # Imprimir mensaje de error si el estado no es el esperado
            print("Error:", response_data.get('message', 'Unknown error'))
        else:
            return response_data  # Devuelve la respuesta en caso de éxito

    except requests.exceptions.RequestException as e:
        # Captura errores de red y otros problemas en la solicitud
        print("Request failed:", e)


# Actualiza el batch y serial
def actualizar_warehouse_sheets(sku, tipo, numero, id):
    for index, record in enumerate(data, start=2):  # Comienza en 2 si tienes encabezado
        if tipo == 'batch' and record.get("Batch") == numero and record.get("SKU") == sku:
            # Convertir las claves en una lista para obtener el índice de "Item_id"
            column_index = list(record.keys()).index("Batch_Id") + 1
            # Actualizar el campo Item_id en la hoja
            sheet.update_cell(index, column_index, id)


# Buscar el Id del batch dentro del Json de respuesta
def find_batch_id_item(item_data, warehouse_id):
    warehouse_id = str(warehouse_id)
    for warehouse in item_data.get("warehouses", []):
        # Verifica si el ID del almacén coincide con el solicitado
        if warehouse.get("warehouse_id") == warehouse_id:
            # Recorre la lista de lotes (batches) en el almacén específico
            for batch in warehouse.get("batches", []):
                # Retorna el batch_in_id del primer lote encontrado                
                return batch.get("batch_in_id")
    # Si no se encuentra el almacén o lote, retorna None
    return None


# Refrescar la base de datos
def extraerBDsheets():
    # Extraer los datos de la hoja BD
    bd_data = sheet_bd.get_all_records()
    df_bd = pd.DataFrame(bd_data).astype({"Item_Id": "string","Batch_Id": "string","Almacen": "string"})
    # Extraer los datos de la hoja Comercial
    bd_comercial = sheet_comercial.get_all_records()
    df_comercial = pd.DataFrame(bd_comercial).astype({"Almacen": "string"})

    # Crear data frame para insertar
    df_insert = pd.DataFrame(columns=df_bd.columns).astype({"Item_Id": "string","Batch_Id": "string","Almacen": "string"})
    # Crear data frame para los sin lote ni serie
    df_no_batch_serial = pd.DataFrame(columns=df_bd.columns).astype({"Item_Id": "string", "Batch_Id": "string", "Almacen": "string"})

    # Parte del codigo que obtiene los items sin ID en la BD
    # Hacer un merge para tener aquellos existentes agregando el valor de item:id en base al SKU
    df_merged = df_comercial.merge(df_bd[['SKU', 'Item_Id']], on='SKU', how='left')

    # Agregar los que no tienen Id a insert
    df_insert = pd.concat([df_insert, df_merged[df_merged['Item_Id'].isna()]], ignore_index=True)

    # Para los SKU que tienen coincidencia, agregar el item_id de df_bd en df_comercial
    df_comercial.loc[df_comercial['SKU'].isin(df_bd['SKU']), 'Item_Id'] = df_merged['Item_Id']

    # Remover los registros sin coincidencia (sin item_id) de df_insert
    df_comercial = df_comercial.dropna(subset=['Item_Id'])

    # Checamos si hay batches con Stock diferente dentro de la base de datos y los datos obtenidos en Comercial
    # Iterar en el df de comercial para saber si tiene batchs en la BD
    for index, row in df_comercial.iterrows():
        batch_comercial = row['Batch']
        serial_comercial = row['Serial']
        item_sku = row['SKU']
        stock_difference = 0

        #Si batch no es vacio
        if batch_comercial != "":
            if batch_comercial in df_bd['Batch'].values:
                # Extraer el Stock de df_bd correspondiente al Batch coincidente
                stock_bd = df_bd.loc[df_bd['Batch'] == batch_comercial, 'Stock'].values[0]
                batch_id = df_bd.loc[df_bd['Batch'] == batch_comercial, 'Batch_Id'].values[0]
                item_id = df_bd.loc[df_bd['Batch'] == batch_comercial, 'Item_Id'].values[0]
                almacen = df_bd.loc[df_bd['Batch'] == batch_comercial, 'Almacen'].values[0]
                
                # Calcular la diferencia de Stock
                stock_difference = stock_bd - row['Stock']
                
                # Checa los que tuvieron un ajuste en base a la diferencia y lo agrega a la insercion
                if stock_difference != 0:
                    row['Ajuste'] = stock_difference
                    row['Batch_Id'] = batch_id
                    row['Item_Id'] = item_id
                    row['Almacen'] = almacen
                    df_insert = pd.concat([df_insert, pd.DataFrame([row])], ignore_index=True)
            else:
                df_insert = pd.concat([df_insert, pd.DataFrame([row])], ignore_index=True)

        # Si serial no es vacio
        elif serial_comercial != "":
            if serial_comercial in df_bd['Serial'].values:
                pass
            else:
                df_insert = pd.concat([df_insert, pd.DataFrame([row])], ignore_index=True)
        
        # si no es ni serial ni batch, concatenar los datos
        else:
            # Crea una fila para revisar si existe en el df
            existing_row = df_no_batch_serial[df_no_batch_serial['SKU'] == item_sku]

            # Si hay contenido
            if not existing_row.empty:
                # Si ya existe, suma el stock
                idx = existing_row.index[0]
                df_no_batch_serial.at[idx, 'Stock'] += row['Stock']
            else:
                # Si no existe, agrégalo como nuevo
                df_no_batch_serial = pd.concat([df_no_batch_serial, pd.DataFrame([row])], ignore_index=True)
    

    for index, row in df_no_batch_serial.iterrows():
        item_sku = row['SKU']
        item_id = row['Item_Id']
        warehouse_id = row['Almacen']

        # Obtiene el item con toda su información
        response = get_Item(item_id, access_token)
        warehouses = response.get('item', {}).get('warehouses', [])

        # Inicializar el stock del almacén como None por si no se encuentra
        actual_stock = None

        # Buscar el stock específico del almacén
        for warehouse in warehouses:
            if warehouse.get('warehouse_id') == warehouse_id:
                actual_stock = warehouse.get('warehouse_available_stock')
                break

        # Verifica si se encontró el stock del almacén
        if actual_stock is None:
            print(f"No se encontró el stock para el almacén {warehouse_id} del item {item_id}")
            df_insert = pd.concat([df_insert, pd.DataFrame([row])], ignore_index=True)
            continue


        else:
            # Calcular la diferencia de stock
            stock_difference = actual_stock - row['Stock']

            # Checar los que tuvieron un ajuste en base a la diferencia y agregarlos a la inserción
            if stock_difference != 0:
                row['Ajuste'] = stock_difference
                row['Item_Id'] = item_id
                row['Almacen'] = warehouse_id
                df_insert = pd.concat([df_insert, pd.DataFrame([row])], ignore_index=True)
    
    # Crear data frame para los registros sobrantes (no se encuentran en df_comercial)
    df_erase_or_adjust = pd.DataFrame(columns=df_bd.columns).astype({"Item_Id": "string","Batch_Id": "string","Almacen": "string"})

    # Iterar en df_bd para identificar lotes y seriales sobrantes
    for index, row in df_bd.iterrows():
        batch_bd = row['Batch']
        serial_bd = row['Serial']
        item_sku = row['SKU']

        # Si batch no es vacio
        if batch_bd != "" and row['Stock'] != 0:
            if batch_bd not in df_comercial['Batch'].values:
                df_erase_or_adjust = pd.concat([df_erase_or_adjust, pd.DataFrame([row])], ignore_index=True)

        # Si serial no es vacio
        elif serial_bd != "":
            if serial_bd not in df_comercial['Serial'].values:
                df_erase_or_adjust = pd.concat([df_erase_or_adjust, pd.DataFrame([row])], ignore_index=True)

        # si no es ni serial ni batch, concatenar los datos
        else:
            df_erase_or_adjust = pd.concat([df_erase_or_adjust, df_bd[~df_bd['Batch'].isin(df_comercial['Batch'].values) & ~df_bd['Serial'].isin(df_comercial['Serial'].values)]], ignore_index=True)

    df_erase_or_adjust['Ajuste'] = df_erase_or_adjust['Stock']
    df_insert = pd.concat([df_insert, df_erase_or_adjust], ignore_index=True)

    sheet.clear()
    set_with_dataframe(sheet, df_insert)


# Actualiza los items en Zoho inventory
def actualizarItems():
    # Extraer los datos de la hoja BD
    bd_data = sheet_bd.get_all_records()
    df_bd = pd.DataFrame(bd_data).astype({"Item_Id": "string","Batch_Id": "string","Almacen": "string"})
    # Extraer los datos de la hoja Comercial
    bd_comercial = sheet_comercial.get_all_records()
    df_comercial = pd.DataFrame(bd_comercial).astype({"Almacen": "string"})

    # Crear data frame para actualizar
    df_update = pd.DataFrame(columns=df_bd.columns).astype({"Item_Id": "string","Batch_Id": "string","Almacen": "string"})

    # Comparar los items de Comercial con los de la BD
    for index, row in df_comercial.iterrows():
        item_sku = row['SKU']

        # Buscar el item con el mismo SKU en BD
        if item_sku in df_bd['SKU'].values:

            # Extraer info de items de df_bd correspondiente al SKU coincidente
            item_name = df_bd.loc[df_bd['SKU'] == item_sku, 'Name'].values[0]
            item_unit = df_bd.loc[df_bd['SKU'] == item_sku, 'Unit'].values[0]
            item_price = df_bd.loc[df_bd['SKU'] == item_sku, 'Price'].values[0]
            item_description = df_bd.loc[df_bd['SKU'] == item_sku, 'Descripcion'].values[0]
            row['Item_Id'] = df_bd.loc[df_bd['SKU'] == item_sku, 'Item_Id'].values[0]

            # Compara el item de Comercial con el de la BD
            if (item_name != row['Name']) or (item_unit != row['Unit']) or (item_price != row['Price'] ) or (item_description == ''):
                print("Actualizacion de item ", item_sku)

                # Declarar cambios
                update_item_name = row['Name']
                update_item_unit = row['Unit']
                update_item_price = row['Price']
                update_item_descripcion = row['Descripcion']

                # Agregar al DF de actualizacion los items que requieren actualizarse en Zoho
                df_update = pd.concat([df_update, pd.DataFrame([row])], ignore_index=True)

                for index, row in df_bd.iterrows():
                    # Si el SKU coincide
                    if item_sku == row['SKU']:
                        # Actualizar las lineas
                        df_bd.at[index, 'Name'] = update_item_name
                        df_bd.at[index, 'Unit'] = update_item_unit
                        df_bd.at[index, 'Price'] = update_item_price
                        df_bd.at[index, 'Descripcion'] = update_item_descripcion

    print(df_update)
    # Escribir df_bd actualizado de vuelta a Google Sheets
    sheet_bd.clear()
    set_with_dataframe(sheet_bd, df_bd)

    # Actualizar cada item de Inventory en base al df de actualizaciones de objetos
    for index, row in df_update.iterrows():
        # Json de Batch Item
        item_data = {
            "name": row['Name'],
            "sku": row['SKU'],
            "rate": row['Price'],
            "unit": row['Unit'],
            "description": row['Descripcion'],
            "is_taxable": 'true',
            "item_type": "inventory",
            "inventory_account_id": "5371960000000034001",
            "inventory_account_name": "Inventory Asset",
        }
        update_item_inventory(item_data, access_token, row['Item_Id'])


# Actualiza la hoja BD para tener los nuevos datos insertados
def actualizarBDsheets():
    # Crear dataframes de los nuevos datos insertados
    data = sheet.get_all_records()
    df_data = pd.DataFrame(data).astype({"Item_Id": "string","Batch_Id": "string","Almacen": "string"})

    # Crear dataframe de la BD para actualizarla
    bd_data = sheet_bd.get_all_records()
    df_bd = pd.DataFrame(bd_data).astype({"Item_Id": "string","Batch_Id": "string","Almacen": "string"})

    # Iterar sobre cada fila de los datos nuevos
    for index, row in df_data.iterrows():
        batch_data = row['Batch']

        # Revisa si esta la fila en la BD
        if batch_data in df_bd['Batch'].values:
            # Obtener el índice de la fila en df_bd
            idx = df_bd.index[df_bd['Batch'] == batch_data].tolist()[0]
            
            # Actualizar el stock en df_bd
            df_bd.at[idx, 'Stock'] = df_bd.at[idx, 'Stock'] - row['Ajuste']      
        
        # Si no esta entonces es un item nuevo
        else:
            sku_data = row['SKU']
            warehouse_data = row['Almacen']

            matching_indices = df_bd.index[(df_bd['SKU'] == sku_data) & (df_bd['Almacen'] == warehouse_data)].tolist()

            if matching_indices:  # Verifica si hay coincidencias
                idx = matching_indices[0]
                df_bd.at[idx, 'Stock'] = row['Stock'] #df_bd.at[idx, 'Stock'] - 
             # Si el batch no existe, agregar una nueva fila a df_bd
            new_row = row.copy()
            new_row['Stock'] = new_row['Stock'] - new_row['Ajuste']  # Ajustar stock inicial
            new_row['Ajuste'] = 0  # Ajuste para la nueva fila es 0
            df_bd = pd.concat([df_bd, pd.DataFrame([new_row])], ignore_index=True)
        
        # Resetear el ajuste a 0 en df_data (opcional si necesitas mantener df_data actualizado)
        df_bd.at[index, 'Ajuste'] = 0
        
    sheet_bd.clear()
    set_with_dataframe(sheet_bd, df_bd)


# -------------------------------------------------------MAIN------------------------------------------------------------------------------------
"""
# Extraemos la info de Comercial y lo ponemos en el sheet
sql_query_foncs()

# Extraer los datos del sheets de Comercial, compararlos con la BD y insertar aquellos con modficaciones
extraerBDsheets()
"""
# Obtener el token de acceso de Zoho
access_token = get_zoho_access_token()

# Leer los datos de la hoja de cálculo de insercion agregados por "extraerBDsheets()"
data = sheet.get_all_records()


try:
    df = pd.DataFrame(data).astype({"Item_Id": "string","Batch_Id": "string","Almacen": "string"})
except:
    # Actualizamos las listas de precios
    sql_query_priceList()
    print("Base de datos sin actualizaciones")
    exit()
"""
# Actualizar los items actuales en base a Comercial
actualizarItems()
"""
# Bandera que detecte cambios en el sheet
flag = True
# Detecta el tipo de almacen
tipo = ''

# Crear artículos en Zoho Inventory a partir de los datos de Google Sheets  {Es batch, es serial, ninguno}
while flag == True:
    flag = False
    for item in data:
        # Buscar si existe el item_id de la fila
        if item['Item_Id'] == '':
            print("Nuevo item ",item["SKU"])
            # No existe
            # Es item de batch
            if item['Batch'] != '':
                # Json de Batch Item
                item_data = {
                    "name": item['Name'],
                    "sku": item['SKU'],
                    "rate": item['Price'],
                    "unit": item['Unit'],
                    "description": item['Descripcion'],
                    "is_taxable": 'true',
                    "item_type": "inventory",
                    "inventory_account_id": "5371960000000034001",
                    "inventory_account_name": "Inventory Asset",
                    "initial_stock": item['Stock'],
                    "initial_stock_rate": 0,
                    "track_batch_number": True,
                        "warehouses": [{
                            "warehouse_id": item['Almacen'],
                            "initial_stock": item['Stock'],
                            "initial_stock_rate": 1,

                            "batches": [{
                                "batch_number": item['Batch'],
                                "in_quantity": item['Stock'],
                                }]
                        }]
                }
                tipo = 'batch'
            # Si el item es un Serial
            elif item['Serial'] != '':
                # JSON Serial
                item_data = {
                    "name": item['Name'],
                    "sku": item['SKU'],
                    "rate": item['Price'],
                    "unit": item['Unit'],
                    "description": item['Descripcion'],
                    "is_taxable": 'true',
                    "item_type": "inventory",
                    "inventory_account_id": "5371960000000034001",
                    "inventory_account_name": "Inventory Asset",
                    "initial_stock": item['Stock'],
                    "initial_stock_rate": 1,
                    "track_serial_number": True,
                        "warehouses": [{
                            "warehouse_id": item['Almacen'],
                            "initial_stock": item['Stock'],
                            "initial_stock_rate": 0,
                            "serial_numbers": [item['Serial']]
                        }]
                }
                tipo = 'serial'
            # Si es Item Solo
            else:
                # JSON de item
                item_data = {
                    "name": item['Name'],
                    "sku": item['SKU'],
                    "rate": item['Price'],
                    "unit": item['Unit'],
                    "description": item['Descripcion'],
                    "is_taxable": 'true',
                    "item_type": "inventory",
                    "inventory_account_id": "5371960000000034001",
                    "inventory_account_name": "Inventory Asset",
                    "initial_stock": item['Stock'],
                    "initial_stock_rate": 1,
                    "warehouses": [{
                            "warehouse_id": item['Almacen'],
                            "initial_stock": item['Stock'],
                            "initial_stock_rate": 1
                    }]
                }

            
            # Crear item en base al JSON creado
            response = create_item_in_zoho(item_data, access_token)
            if response is None:
                print("response is none")
                pass
            elif response == "Existe":
                item_id = itemExist(item['SKU'], access_token)
                actualizar_sheets(item['SKU'], item_id)
            else:
                # Actualizamos el Sheet conforme a los id de item y de batch
                actualizar_sheets(item['SKU'], response.get('item').get('item_id'))
                
                if item['Batch'] != '':
                    # Sacamos el id del batch
                    batch_id =find_batch_id_item(response.get('item'),item['Almacen'])
                    # Actualizamos ahora la parte de inventario
                    actualizar_warehouse_sheets(item['SKU'], tipo, item['Batch'], batch_id)
                    
            # Si hubo una actualizacion reiniciamos el ciclo con cambios
            flag = True
            data = sheet.get_all_records()
            break


print("Tocan los batches")
# Depuramos los items existentes para no gastar APIS y haccer solo ajustes de inventario  {Es batch, es Serial, Ninguno}
for item in data:
    # Checamos si el item ya fue agregado previamente
    if item['Item_Id'] != '':
        #Si stock es 0 se omite
        if item['Stock'] == 0:
            pass

        # Checamos si es de Batch
        if item['Batch'] != '':
            # Checamos no existe el Batch en el almacen del producto
            if item['Batch_Id'] == '':
                print("Nuevo Batch", item['Batch'])
                # Json de Batch Item
                print(dt.date.today().isoformat())
                item_data = {
                    "date": dt.date.today().isoformat(),
                    "reason": "Batch update",
                    "adjustment_type": "quantity",
                    "line_items":[{
                        "item_id": item['Item_Id'],
                        "quantity_adjusted": item['Stock'], 
                        "warehouse_id": item['Almacen'],
                        "batches": [{
                            "batch_number": item['Batch'],
                            "in_quantity": item['Stock'],
                            }],
                        }]
                    }

                # Creamos el ajuste de inventario
                response = inventory_adjustement(item_data, access_token)
                # Agregamos el batch_id para su actualizacion
                if response is None:
                    pass

                else:
                    batch_in_id = response['inventory_adjustment']['line_items'][0]['batches'][0]['batch_in_id']
                    print(batch_in_id)

                    # Actualizamos ahora la parte de inventario
                    actualizar_warehouse_sheets(item['SKU'], 'batch', item['Batch'], batch_in_id)
                    time.sleep(1)

            # Existe el Batch en el almacen del producto y tiene un ajuste de salida (Positivo)
            elif item['Ajuste'] > 0:
                print("Ajuste de Batch Existente", item['Batch'])
                # Json de Batch Item Existente "batch_in_id": item['Batch_Id'] 
                item_data = {
                    "date": dt.date.today().isoformat(),
                    "reason": "Batch update",
                    "adjustment_type": "quantity",
                    "line_items":[{
                        "item_id": item['Item_Id'],
                        "quantity_adjusted": -item['Ajuste'], 
                        "warehouse_id": item['Almacen'],
                        "batches": [{
                            "batch_in_id": item['Batch_Id'],
                            "out_quantity": item['Ajuste'],
                            }],
                        }]
                    }
                
                # Creamos el ajuste de inventario
                response = inventory_adjustement(item_data, access_token)
                # Agregamos el batch_id para su actualizacion
                if response is None:
                    pass
                batch_in_id = response['inventory_adjustment']['line_items'][0]['batches'][0]['batch_in_id']

                # Actualizamos ahora la parte de inventario
                actualizar_warehouse_sheets(item['SKU'], 'batch', item['Batch'], batch_in_id)
                time.sleep(5)

            # Existe el Batch en el almacen del producto y tiene un ajuste de entrada (Negativo)
            elif item['Ajuste'] < 0:
                print("Ajuste de Batch Existente", item['Batch'])
                pass
                # Json de Batch Item Existente "batch_in_id": item['Batch_Id'] 
                item_data = {
                    "date": dt.date.today().isoformat(),
                    "reason": "Batch update",
                    "adjustment_type": "quantity",
                    "line_items":[{
                        "item_id": item['Item_Id'],
                        "quantity_adjusted": -item['Ajuste'], 
                        "warehouse_id": item['Almacen'],
                        "batches": [{
                            "batch_in_id": item['Batch_Id'],
                            "in_quantity": item['Ajuste'],
                            }],
                        }]
                    }
                
                # Creamos el ajuste de inventario
                response = inventory_adjustement(item_data, access_token)
                # Agregamos el batch_id para su actualizacion
                if response is None:
                   pass
                batch_in_id = response['inventory_adjustment']['line_items'][0]['batches'][0]['batch_in_id']

                # Actualizamos ahora la parte de inventario
                actualizar_warehouse_sheets(item['SKU'], 'batch', item['Batch'], batch_in_id)
                time.sleep(5)

            # Si tiene batch y no tiene ajuste se salta    
            else:
                pass

        # Checamo si es de Serial:
        elif item['Serial'] != '':
            # Json de Serial Item
            item_data = {
                "date": dt.date.today().isoformat(),
                "reason": "Serial Number Adjustment",
                "line_items": [{
                    "item_id": item['Item_Id'],
                    "quantity_adjusted": -item['Stock'],
                    "warehouse_id": item['Almacen'],
                    "serial_numbers": [item['Serial']]
                }]
            }

            # Actualizamos el item
            response = inventory_adjustement(item_data, access_token)
            time.sleep(1)

        
        # Si no es serial ni Batch
        else:
            # JSON de InventoryAdjustment
            item_data = {
                "date": dt.date.today().isoformat(),
                "reason": "Ajuste de Inventario",
                "line_items": [{
                    "item_id": item['Item_Id'],
                    "quantity_adjusted": item['Stock'],
                    "warehouse_id": item['Almacen'],
                }]
            }

            # Actualizamos el item
            response = inventory_adjustement(item_data, access_token)
            time.sleep(1)

print("actualizar")
actualizarBDsheets()

# Actualizamos las listas de precios
sql_query_priceList()