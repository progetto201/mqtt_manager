MQTT_MANAGER
============

Sezioni
-------

-  `Introduzione`_
-  `Guida all’uso`_
-  `Descrizione`_
-  `Sviluppo e espansione`_
-  `Requisiti`_
-  `Changelog`_
-  `Autore`_

.. raw:: html
   
   <hr width="100%" size="140px">

Introduzione
------------

Lo script si occupa di **connettersi al database e al broker MQTT**. A
connessione avvenuta **si iscrive ai topic** di presentazione e dei dati e
**gestisce tutti i messaggi** che arrivano.

.. raw:: html
   
   <hr width="100%" size="140px">

Guida all’uso
-------------

Creare un file di configurazione con la seguente struttura:

::

   [Database]
   username = <username DB>
   password = <password DB>
   host = <dominio/IP DB>
   database = <nome DB>

   [MQTT broker]
   username = <username MQTT>
   password = <password MQTT>
   host = <dominio/IP MQTT>
   port = <porta MQTT>

Inserire il percorso del file di configurazione nella variabile "configfile_path".

Eseguire all’avvio di raspberry pi lo script per permettergli di
connettersi al broker MQTT e gestire i dati provenienti dai “dataclient”

.. raw:: html
   
   <hr width="100%" size="140px">


Descrizione
-----------

Per la documentazione del codice funzione per funzione andare in `questa pagina`_

1. Connessione a database e MQTT broker

   .. raw:: html 
         :file: docs/assets/mysql_conn.svg
   
   .. raw:: html
         :file: ../docs/assets/mysql_conn.svg

   Lo script si connette al database attraverso la funzione
   ``mysql_conn()``, crea il cursore che richiede le `prepared
   statements`_

   .. raw:: html 
         :file: docs/assets/mqtt_conn.svg
   
   .. raw:: html
         :file: ../docs/assets/mqtt_conn.svg

   e si connette al broker MQTT usando la funzione ``mqtt_conn()``. Da
   questo punto il client MQTT rimarra’ in ascolto di messaggi in
   arrivo. 
   
   .. note:: Il resto del codice nel main serve a controllare eventuali
             errori e nel caso chiudere la connessione al database. Nel corso del
             programma NIENTE dovrebbe permettere questo ad eccezione di errori di
             connessione al database e al broker MQTT.

2. La funzione di callback ``on_connect()`` si iscrive ai “maintopic”

   .. raw:: html
         :file: docs/assets/on_connect.svg
      
   .. raw:: html
         :file: ../docs/assets/on_connect.svg

   .. note:: I maintopic sono i topic riconosciuti dal programma 
             (attualmente “data/+” e “presentation/+”)

3. La funzione di callback ``on_message()`` riceve i messaggi dai “dataclient”:

   .. raw:: html
         :file: docs/assets/on_message.svg
      
   .. raw:: html
         :file: ../docs/assets/on_message.svg

   Controlla che il topic sia valido (formato
   ``<maintopic>/<macaddress>``) e che il mac address sia valido, infine
   richiama la corretta funzione in base al topic del messaggio.
   Attualmente il programma richiama:

   -  ``manage_data()`` se il topic e’ ``data/<macaddress``
   -  ``manage_presentation()`` se il topic e’
      ``presentation/<macaddress``

4. I dataclient inviano per primo il messaggio di presentazione,
quindi ``on_message()`` richiama la funzione ``manage_presentation()``

   .. raw:: html
         :file: docs/assets/manage_presentation.svg
      
   .. raw:: html
         :file: ../docs/assets/manage_presentation.svg

   La funzione controlla che l'IP sia valido e che i mac address
   nel topic e nel messaggio corrispondino, infine
   cerca di ottenere dal database dati relativi al nodo
   per riconoscere se e' nuovo o no usando la funzione ``get_node()``.

   Se il nodo e' nuovo viene richiamata la funzione ``present_newnode()``,
   altrimenti viene richiamata la funzione ``present_oldnode()``.

5. Il nodo alla prima presentazione e' nuovo: viene richiamata la funzione ``present_newnode()``:

   .. raw:: html
         :file: docs/assets/present_newnode.svg
      
   .. raw:: html
         :file: ../docs/assets/present_newnode.svg

   La funzione recupera dal database il tipo di nodo (usando la funzione ``get_type()``)
   per assicurarsi che e' riconosciuto dal sistema:
   se esiste viene inserito un record nella tabella dei nodi,
   viene verificato il successo dell'operazione
   e ottiene con la funzione ``get_node()`` l'id del nodo appena aggiunto.
   
   .. note:: viene verificato il successo anche di questa operazione

   Infine viene richiamata la funzione ``add_newnode_options()``
   per aggiungere le impostazioni del nodo nella tabella corretta

6. La funzione ``add_newnode_options()`` sceglie in base al tipo
di nodo (contenuto nel messaggio MQTT) quale funzione richiamare per inserire nel database le impostazioni

7. La funzione ``add_newnode_options_typeX()`` viene richiamata:
   
   ottiene dal messaggio le impostazioni da inserire
   nel database e le inserisce eseguendo una INSERT

8. Da questo momento il nodo comincera' a inviare dati da inserire nel database,
la funzione ``manage_data()`` verra' richiamata da ``on_message()``

   .. raw:: html 
         :file: docs/assets/manage_data.svg
   
   .. raw:: html
         :file: ../docs/assets/manage_data.svg

   La funzione ``manage_data()`` richiama la funzione ``get_node()`` per ottenere
   l'id del nodo e il tipo.

   In base al tipo viene richiamata la funzione corretta per inserire
   i dati nel database, ``manage_data_typeX()``

   .. note:: Dove "X" e' il tipo di nodo, ex. ``manage_data_type0()``

9. Se il nodo si disconnette dal WiFi o dal broker MQTT cerchera' di riconnettersi:

   Il nodo si ri-presentera' al sistema, la funzione ``on_message()`` richiamera'
   la funzione ``manage_presentation()`` che richiamera' la funzione ``present_oldnode()``.

   La funzione richiamera' la funzione ``get_node()`` per ottenere i dati del nodo sul database,
   poi controlla se le informazioni sono aggiornate o no.

   Se le informazioni non sono aggiornate verra' eseguita una istruzione SQL di UPDATE
   per aggiornarle.

   Dopo il controllo viene richiamata la funzione ``get_options()`` che restituisce
   le impostazioni e poi le invia al "dataclient" via messaggio MQTT.

   La funzione ``get_options()`` decide in base al tipo di nodo quale funzione richiamare.
   Il nome della funzione e' nel formato ``get_options_typeX()`` e si occupa
   di restituire una stringa con le impostazioni in JSON.

   .. note:: Dove "X" e' il tipo di nodo, ex. ``manage_data_type0()``

.. raw:: html
   
   <hr width="100%" size="140px">

Sviluppo e espansione
---------------------

Per aggiungere nuovi tipi di “dataclient”: 

1. Creare il record nella tabella “t_types” con i dettagli del nuovo nodo:

   La tabella e' strutturata nel seguente nodo:

   +------------------------------+-----------------------------------------------+---------------------------+
   | id                           | description                                   |  category_id              |
   +==============================+===============================================+===========================+
   | **INT()** identificativo tipo| **VARCHAR(255)** informazioni sul tipo di nodo|**INT()** sensore/attuatore|
   +------------------------------+-----------------------------------------------+---------------------------+

   Aggiungere un record con un id diverso da quelli esistenti,
   una descrizione che descrive il tipo di nodo

   Formato consigliato: 
   
   ::

      <numero sensori/attuatori> <sigla sensore/attuatore>: <dato ricevuto 1>, <dato ricevuto 2>, ...
   

   .. note:: Il numero dei sensori/attuatori puo' essere omesso se e' "1"

   e infine un id della categoria:
      
   - **0** per sensori
   - **1** per attuatori

   .. note:: Per aggiungere altri tipi di categoria creare un record
            nella tabella t_categories

2. Creare tabella dei dati del tipo di sensore:

   Si consiglia di mantenere il formato del nome della tabella
   ``t_type<id tipo nodo>_data``
   
   .. note:: dove ``<id tipo nodo>`` e’ l’identificativo del tipo di nodo

   Come campi utilizzare:

   -  campo “id” INT() e AUTOINCREMENT: identificativo del record
   -  campo “node_id” INT(): identificativo del nodo che ha inviato i
      dati
   -  campo “tstamp” INT(): timestamp dell’inserimento dei dati >
      Calcolato dalla funzione che inserisce i dati
   -  campo “rssi” INT(): valore RSSI


   Aggiungere poi tutti i campi necessari per memorizzare i dati
   specifici del tipo di nodo 
   
   .. note:: es. temperatura e umidita’ per i DHT22

3. Creare tabella delle opzioni del tipo di sensore:

   Si consiglia di mantenere il formato del nome della tabella
   ``t_type<id tipo nodo>_options`` 
   
   .. note:: dove ``<id tipo nodo>`` e’ l’identificativo del tipo di nodo

   Come campi utilizzare:

   -  campo “node_id” INT(): identificativo del nodo

   Aggiungere poi tutti i campi necessari per memorizzare le
   impostazioni specifiche del tipo di nodo

4. Modificare lo script mqtt_manager per gestire i dati:

   nella funzione ``manage_data()`` aggiungere un’istruzione if/elif per
   riconoscere il node_type (tipo di nodo) e richiamare una funzione
   ``manage_data_typeX()`` > Dove “X” e’ il tipo di nodo.

   ex.

   ::  
      
      if node_type == 0:      
         manage_data_type0(node_id, t_msg)  
      elif node_type == 1:      
         manage_data_type1(node_id, t_msg)  
      elif node_type == 2:      
         manage_data_type2(node_id, t_msg)  
      ...
   
   Creare la funzione ``manage_data_typeX()`` prendendo come esempio ``manage_data_type0()``:

   ::
   
      timestamp = int(time.time())
      try:
         # ottieni dal messaggio dato1, dato2 e rssi 
         dato1 = t_msg[“dato1”] 
         dato2 = t_msg[“dato2”] 
         rssi = t_msg[“rssi”]

         # inserisci i dati nella tabella dei dati di tipo X
         query = "INSERT INTO t_typeX_data (tstamp, node_id, dato1, dato2, rssi) VALUES (%s, %s, %s, %s, %s)"
         cursor.execute(query, [timestamp, t_nodeid, dato1, dato2, rssi])
         conn.commit()

      except Exception as t_e:
         logger("ERROR: manage_data_typeX() errore sconosciuto sulla riga '{}': '{}'".format(sys.exc_info()[2].tb_lineno,
                                                                                             t_e),
               logfile)
    
5. Modificare lo script mqtt_manager per gestire l'inserimento delle impostazioni di default degli sketch:

   Nella funzione ``add_newnode_options()`` aggiungere un'istruzione if/elif per riconoscere il node_type (tipo di nodo)
   e richiamare una funzione ``add_newnode_options_typeX()``
   
   .. note:: Dove "X" e' il tipo di nodo.
    
   ::
   
      if node_type == 0:
         add_newnode_options_type0(node_id, t_msg)
      elif node_type == 1:
         add_newnode_options_type1(node_id, t_msg)
      elif node_type == 2:
         add_newnode_options_type2(node_id, t_msg)
      ...
    
   Creare la funzione ``add_newnode_options_typeX()``
   prendendo come esempio ``add_newnode_options_type0()``:
    
   ::
   
      try:
         # se il node type e' X, il nodo ha inviato "qualcosa"
         qualcosa = t_msg["qualcosa"]

         # inserisci nella tabella delle impostazioni nodi di tipo X "qualcosa"
         query = "INSERT INTO t_typeX_options (node_id, qualcosa) VALUES (%s, %s)"
         cursor.execute(query, [t_nodeid, qualcosa])
         conn.commit()
    
      except Exception as t_e:
         logger("ERROR: add_newnode_options_typeX(), errore sconosciuto sulla riga '{}': {}".format(
               sys.exc_info()[2].tb_lineno, t_e),
               logfile)
   
6.  Modificare lo script mqtt_manager per gestire l'invio delle impostazioni dal database al nodo:

   Nella funzione ``get_options()`` aggiungere un'istruzione if/elif per riconoscere il node_type (tipo di nodo)
   e richiamare una funzione ``get_options_typeX()``
   
   .. note:: Dove "X" e' il tipo di nodo.

   ::
   
      if node_type == 0:
         get_options_type0(t_nodeid)
      elif node_type == 1:
         get_options_type1(t_nodeid)
      elif node_type == 2:
         get_options_type2(t_nodeid)
      ...
   
    
   Creare la funzione ``get_options_typeX()``
   prendendo come esempio ``get_options_type0()``:
    
   ::

      options = None

      try:
         query = "SELECT node_id, qualcosa FROM t_typeX_options WHERE node_id = %s"
         cursor.execute(query, [t_nodeid])
         options_data = cursor.fetchall()

         if len(options_data) == 1:
            options = "{'qualcosa': " + str(options_data[0][1]) + "}"
         else:
            logger("WARNING: numero opzioni del nodo '{}' errato".format(t_nodeid), logfile)

      except Exception as t_e:
         logger("ERROR: get_options_typeX(), errore sconosciuto sulla riga '{}': {}".format(sys.exc_info()[2].tb_lineno,
                                                                                     t_e),
               logfile)

      return options

Requisiti
---------

- python 3
- libreria paho-mqtt
- libreria mysql-connector

Changelog
---------

**01_01 2020-02-26**:

Primo commit

Autore
------
Zenaro Stefano

.. _Introduzione: #introduzione

.. _Guida all uso: #guida-alluso

.. _Descrizione: #descrizione

.. _Sviluppo e espansione: #sviluppo-e-espansione

.. _Requisiti: #requisiti

.. _Changelog: #changelog

.. _Autore: #autore

.. _prepared statements: https://www.html.it/pag/63163/mysqli-e-i-prepared-statement/

.. _questa pagina: https://progetto201.github.io/mqtt_manager/