#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
MQTT_MANAGER: gestisce i messaggi MQTT dei nodi

Lo script si occupa di connettersi al database e al broker MQTT.
A connessione avvenuta si iscrive ai topic di presentazione e dei dati
e gestisce tutti i messaggi che arrivano.

on_message() riceve i messaggi e li passa in base al topic alle funzioni:

- :func:`manage_data()`: gestisce i messaggi con i dati dei nodi

- :func:`manage_presentation()`: gestisce i messaggi di presentazione dei nodi

"""
__author__ = "Zenaro Stefano"
__version__ = "01_01 2020-02-23"

import paho.mqtt.client as mqtt
import mysql.connector
import json
import time
import re
import sys
import ipaddress
import os
import configparser

boold = False  # True = visualizza messaggi di debug
conn = None  # oggetto connessione mysql

configfile_path = "config.ini"

##################################################################################################################
#                                                                                                                #
#                                                    MQTT FUNCTIONS                                              #
#                                                                                                                #
##################################################################################################################


def on_connect(t_client, userdata, flags, rc):
    """
    A connessione con il broker MQTT avvenuta si iscrive ai maintopic.

    Un for loop fa iscrivere il client a tutti i maintopic in <maintopics>
    
    :param t_client: client MQTT
    :param userdata:
    :param flags:
    :param rc: codice di stato
    """

    logger("Connesso con codice stato: " + str(rc), logfile)

    try:
        # iscriviti ai maintopic
        for maintopic in maintopics:
            logger("Iscritto al maintopic: " + maintopic["name"] + "/+", logfile)
            t_client.subscribe(maintopic["name"] + "/+")

    except Exception as t_e:
        logger("ERROR: on_connect(), errore sconosciuto sulla riga '{}': {}".format(sys.exc_info()[2].tb_lineno, t_e),
               logfile)


def on_message(t_client, userdata, msg):
    """
    Gestisce i messaggi arrivati e li passa alla funzione corretta.

    La funzione cerca di ottenere dal topic del messaggio MQTT
    il "maintopic" (primo livello del topic) e l'indirizzo MAC (secondo livello del topic).

    Dopo aver suddiviso i livelli del topic la funzione decodifica il messaggio JSON proveniente dal nodo,
    si assicura che il topic sia strutturato in maniera adeguata: <maintopic>/<macaddress>,
    verifica con valid_mac() se l'indirizzo MAC <macaddress> e' valido e infine
    controlla se il <maintopic> e' riconosciuto dal programma (e' presente in <maintopics>).

    Se il maintopic e' riconosciuto allora viene richiamata la sua funzione:
    - maintopic "presentation": viene richiamata la funzione manage_presentation()
    - maintopic "data": viene richiamata la funzione manage_data()

    :param t_client: client MQTT
    :param userdata:
    :param msg: messaggio MQTT, contiene stringa JSON
    """

    try:
        # dividi maintopic dal mac address
        topic_split = msg.topic.split("/")

        # decodifica il messaggio
        message = json.loads(msg.payload.decode())

        logger("Nuovo messaggio sul topic: {} ({})".format(msg.topic, message), logfile)
        
        # dovrebbe contenere due elementi
        if len(topic_split) == 2:
            logger("Formato topic '{}' valido".format(msg.topic), logfile)
            # memorizza topic e mac address
            message_topic = topic_split[0]
            macaddr = topic_split[1]

            # verifica che il mac address sia valido
            if valid_mac(macaddr):
                logger("MAC address '{}' valido".format(macaddr), logfile)
                # controlla il maintopic
                found_maintopic = False  # maintopic trovato
                i = 0  # contatore

                # continua a scorrere i maintopic fino a fine array
                # o finche' non si trova il maintopic giusto
                while i < len(maintopics) and not found_maintopic:
                    # se il nome del maintopic corrisponde al topic del messaggio
                    # gestiscilo con la funzione adatta
                    if maintopics[i]["name"] == message_topic:
                        logger("Maintopic '{}' valido".format(message_topic), logfile)
                        found_maintopic = True
                        maintopics[i]["function"](macaddr, message)

                    i += 1

                # se il maintopic non e' stato trovato salva messaggio di log
                if not found_maintopic:
                    logger("WARNING: Maintopic '{}' non trovato".format(message_topic), logfile)

            # MAC address non valido
            else:
                logger("WARNING: mac address '{}' non valido".format(macaddr), logfile)

        # formato topic non valido
        else:
            logger("WARNING: formato topic '{}' non valido".format(msg.topic), logfile)

    except Exception as t_e:
        logger("ERROR: on_message(), errore sconosciuto sulla riga '{}': {}".format(sys.exc_info()[2].tb_lineno, t_e),
               logfile)


def on_disconnect(t_client, userdata, rc=0):
    """
    Funzione richiamata in caso di disconnessione.

    Questa funzione non dovrebbe essere richiamata MAI.

    :param t_client: client MQTT
    :param userdata:
    :param rc: status disconnessione
    """
    logger("Disconnesso con codice: " + str(rc), logfile)
    t_client.loop_stop()


##################################################################################################################
#                                                                                                                #
#                                             DATA MANAGEMENT FUNCTIONS                                          #
#                                                                                                                #
##################################################################################################################


def manage_data(t_macaddr, t_msg):
    """
    Gestisce i messaggi MQTT con dati.

    ottiene id e tipo di nodo dal database e gestisce
    i dati attraverso la funzione adatta:
    - per i nodi di tipo 0 viene richiamata la funzione manage_data_type0()

    :param str t_macaddr: stringa, indirizzo MAC
    :param dict t_msg: messaggio MQTT decodificato
    """
    try:
        # ottieni dati nodo
        node_data = get_node(t_macaddr)

        # controlla quantita' dati ottenuta del nodo
        if len(node_data) == 1:
            node_id = node_data[0][0]
            node_type = node_data[0][2]

            if node_type == 0:
                manage_data_type0(node_id, t_msg)
            else:
                # tipo sconosciuto: non e' supportato dal sistema e occorre aggiungerlo al DB
                logger("WARNING: tipo nodo '{}' sconosciuto, non e' possibile inserire i dati".format(node_type),
                       logfile)
        else:
            logger("WARNING: manage_data(), numero informazioni nodo '{}' irregolare".format(t_macaddr), logfile)

    # errore sconosciuto
    except Exception as t_e:
        logger("ERROR: manage_data() errore sconosciuto sulla riga '{}': '{}'".format(sys.exc_info()[2].tb_lineno, t_e),
               logfile)


def manage_data_type0(t_nodeid, t_msg):
    """
    Inserisce i dati dei nodi di tipo 0 nel database.

    Esegue l'istruzione SQL per inserire i dati.

    :param int t_nodeid: identificativo del nodo
    :param dict t_msg: messaggio MQTT decodificato
    """
    timestamp = int(time.time())

    try:
        # ottieni dal messaggio temperatura, umidita' e rssi
        temp = t_msg["temperature"]
        hum = t_msg["humidity"]
        rssi = t_msg["rssi"]

        # inserisci i dati nella tabella dei dati di tipo 0
        query = "INSERT INTO t_type0_data (tstamp, node_id, temp, hum, rssi) VALUES (%s, %s, %s, %s, %s)"
        cursor.execute(query, [timestamp, t_nodeid, temp, hum, rssi])
        conn.commit()

    except Exception as t_e:
        logger("ERROR: manage_data_type0() errore sconosciuto sulla riga '{}': '{}'".format(sys.exc_info()[2].tb_lineno,
                                                                                            t_e),
               logfile)


##################################################################################################################
#                                                                                                                #
#                                        PRESENTATION MANAGEMENT FUNCTIONS                                       #
#                                                                                                                #
##################################################################################################################


def manage_presentation(t_macaddr, t_msg):
    """
    Gestisce i messaggi di presentazione.

    Recupera dal messaggio ip e mac address del nodo,
    controlla se l'ip e' valido e si assicura che il mac address
    nel messaggio corrisponda a quello del topic.
    La funzione prova infine a ottenere le informazioni del nodo dal database:
    se esistono viene richiamata la funzione present_oldnode(),
    se non esistono viene richiamata la funzione present_newnode()
    > Se il nodo e' duplicato non viene richiamata alcuna funzione

    :param str t_macaddr: stringa, indirizzo MAC
    :param dict t_msg: messaggio MQTT decodificato
    """
    logger("Nuovo messaggio di presentazione del dispositivo '{}': {}".format(t_macaddr, t_msg), logfile)

    ip = None
    try:
        # ottieni dati dal messaggio
        ip = t_msg["ip"]
        mac = t_msg["mac"]

        # controlla se l'indirizzo IP e' valido
        ipaddress.ip_address(ip)

        # controlla che mac address nel topic e nel messaggio sono uguali
        if t_macaddr == mac:
            # cerca di ottenere informazioni dal database sul nodo
            oldinfo_node = get_node(t_macaddr)

            logger("Vecchie informazioni del nodo: '{}'".format(oldinfo_node), logfile)

            # il nodo non esiste sul database
            if len(oldinfo_node) == 0:
                present_newnode(t_msg)

            # il nodo esiste sul database
            elif len(oldinfo_node) == 1:
                present_oldnode(t_msg)

            # il nodo e' duplicato
            else:
                logger("WARNING: nodo '{}' duplicato".format(t_macaddr), logfile)

    # IP non valido
    except ValueError as t_e:
        logger("ERROR: IP '{}' del nodo '{}' non valido: '{}'".format(ip, t_macaddr, t_e), logfile)

    # JSON non ha ip, mac o nodetype
    except KeyError as t_e:
        logger("ERROR: mancano informazioni relative al nodo '{}': '{}'".format(t_macaddr, t_e), logfile)

    # errore sconosciuto
    except Exception as t_e:
        logger(
            "ERROR: manage_presentation() errore sconosciuto sulla riga '{}': '{}'".format(sys.exc_info()[2].tb_lineno,
                                                                                           t_e), logfile)


####################
#
# NEW NODE FUNCTIONS
#
####################


def add_newnode_options(t_nodeid, t_msg):
    """
    Inserisce nella tabella opzioni del nodo le nuove impostazioni.

    La funzione viene richiamata quando viene aggiunto un nuovo nodo
    al sistema e occorre recuperare le impostazioni di default impostate nello sketch:

    viene recuperato dal messaggio il tipo di nodo e in base a questo viene
    richiamata la funzione adatta:

    - se il tipo di nodo e' 0: DHT22, richiama :func:`add_newnode_options_type0()`

    :param int t_nodeid: intero, id nodo da passare alla funzione specifica per il tipo di nodo
    :param dict t_msg: dizionario, messaggio MQTT decodificato proveniente dal nodo
    """
    logger("Aggiungo impostazioni del nodo con id: '{}'".format(t_nodeid), logfile)

    try:
        # ottengo dal messaggio il tipo di nodo
        node_type = t_msg["nodeType"]

        # richiamo la funzione adatta al tipo di nodo per inserire le impostazioni nel DB
        if node_type == 0:
            # tipo 0: DHT22
            add_newnode_options_type0(t_nodeid, t_msg)
        else:
            # tipo sconosciuto: non e' supportato dal sistema e occorre aggiungerlo al DB
            logger("WARNING: impostazioni sconosciute per il tipo nodo '{}'".format(t_nodeid), logfile)

    except Exception as t_e:
        logger(
            "ERROR: add_newnode_options(), errore sconosciuto sulla riga '{}': {}".format(sys.exc_info()[2].tb_lineno,
                                                                                          t_e),
            logfile)


def add_newnode_options_type0(t_nodeid, t_msg):
    """
    Inserisce nella tabella opzioni del nodo di tipo 0 le nuove impostazioni.

    La funzione, richiamata da :func:`add_newnode_options()`, si occupa
    di recuperare dal messaggio MQTT le impostazioni di default dello sketch
    e di inserirle nella tabella del tipo adatto.

    In questo caso il tipo e' 0, quindi si tratta di un nodo con DHT22
    che invia il tempo da aspettare tra le rilevazioni:
    viene inserito nel database insieme all'id del nodo.

    :param int t_nodeid: intero, id del nodo
    :param dict t_msg: dizionario, messaggio MQTT decodificato
    """
    try:
        # se il node type e' 0, il nodo ha inviato il tempo di aspettare tra le rilevazioni
        timebetweenread = t_msg["sketchTimeToWait"]

        # inserisci nella tabella delle impostazioni nodi di tipo 0 il timebetweenread
        query = "INSERT INTO t_type0_options (node_id, timebetweenread) VALUES (%s, %s)"
        cursor.execute(query, [t_nodeid, timebetweenread])
        conn.commit()
    except Exception as t_e:
        logger("ERROR: add_newnode_options_type0(), errore sconosciuto sulla riga '{}': {}".format(
            sys.exc_info()[2].tb_lineno, t_e),
            logfile)


def present_newnode(t_msg):
    """
    Aggiunge il nuovo nodo alla tabella dei nodi nel DB.

    La funzione ottiene informazioni sul tipo di nodo che ha inviato
    il messaggio e inserisce nella tabella nodi l'ip, id del tipo,
    mac e location_id a 0 (sconosciuta).

    Dopo aver inserito il nodo nella tabella vengono aggiunge le
    impostazioni del nodo nella tabella adatta attraverso
    la funzione :func:`add_newnode_options()`

    :param dict t_msg: messaggio MQTT decodificato
    """
    try:
        ip = t_msg["ip"]
        mac = t_msg["mac"]
        node_type = t_msg["nodeType"]

        # ottieni informazioni del tipo di nodo
        nodetype_data = get_type(node_type)

        # se il tipo di nodo e' conosciuto
        if len(nodetype_data) == 1:
            # inserisci in t_nodi: ip, id del tipo, mac e location_id=0
            query = "INSERT INTO t_nodi (ip, type_id, mac, location_id) VALUES (%s, %s, %s, 0)"
            cursor.execute(query, (ip, node_type, mac))

            # controllo se il nodo e' stato inserito correttamente
            if cursor.rowcount == 1:
                conn.commit()  # confermo modifiche del DB

                # ottengo informazioni del node aggiunto per l'id
                node_data = get_node(mac)

                # controllo se ho ottenuto il numero giusto di dati (1)
                if len(node_data) == 1:
                    # creo il record nella tabella impostazioni
                    node_id = node_data[0][0]  # id del nodo creato
                    add_newnode_options(node_id, t_msg)
                else:
                    # la tabella dei nodi contiene duplicati del nodo
                    logger("WARNING: nodo '{}' NON inserito CORRETTAMENTE".format(mac), logfile)
            else:
                # l'insert non ha inserito il record
                logger("WARNING: nodo '{}' NON inserito".format(mac), logfile)
        else:
            # il tipo di nodo non e' conosciuto o e' duplicato
            logger("WARNING: tipo nodo '{}' non conosciuto".format(node_type), logfile)

    except Exception as t_e:
        logger("ERROR: present_newnode(), errore sconosciuto sulla riga '{}': {}".format(sys.exc_info()[2].tb_lineno,
                                                                                         t_e),
               logfile)


####################
#
# OLD NODE FUNCTIONS
#
####################


def present_oldnode(t_msg):
    """
    Aggiorna le informazioni del node sul DB e invia al node le impostazioni

    Verifica se ip e node_type sono aggiornati: se lo sono manda direttamente le impostazioni al node,
    altrimenti aggiorna con l'istruzione SQL update il database e poi gli manda le impostazioni.
    > Le impostazioni vengono recuperate dal database con la funzione :func:`get_options()`

    :param dict t_msg: messaggio MQTT decodificato
    """
    try:
        # recupera dal messaggio ip, mac, tipo di nodo
        ip = t_msg["ip"]
        mac = t_msg["mac"]
        node_type = t_msg["nodeType"]

        # ottieni vecchi dati del node dal DB
        oldnode_data = get_node(mac)
        oldnode_ip = oldnode_data[0][1].decode()
        oldnode_type = oldnode_data[0][2]

        if oldnode_ip == ip and oldnode_type == node_type:
            # le informazioni sul database sono aggiornate, manda le impostazioni
            logger("Le informazioni del nodo sono gia' aggiornate", logfile)

            # ottieni le impostazioni dal DB e mandale al nodo (se restituite da get_options())
            options = get_options(oldnode_data[0][0], node_type)
            if options:
                client.publish("options/" + mac, options)
        else:
            # le informazioni non sono aggiornate, aggiorna ip e tipo id dove mac = <mac>
            query = "UPDATE t_nodi SET t_nodi.ip = %s, t_nodi.type_id = %s WHERE t_nodi.mac = %s"
            cursor.execute(query, (ip, node_type, mac))
            if cursor.rowcount == 1:
                # se l'aggiornamento ha avuto successo, conferma modifiche
                conn.commit()

                # ottieni impostazioni del nodo e mandagliele
                options = get_options(oldnode_data[0][0], node_type)
                if options:
                    client.publish("options/" + mac, options)
            else:
                logger("WARNING: aggiornamento dati del nodo '{}' fallito".format(mac), logfile)

    except Exception as t_e:
        logger("ERROR: present_oldnode(), errore sconosciuto sulla riga '{}': {}".format(sys.exc_info()[2].tb_lineno,
                                                                                         t_e),
               logfile)


def get_options(t_nodeid, t_nodetype):
    """
    Restituisce le impostazioni del nodo <t_nodeid> del tipo <t_nodetype>.

    Con il tipo di nodo <t_nodetype> viene scelta la funzione
    corretta da richiamare per ottenere le impostazioni del nodo <t_nodeid>.

    :param int t_nodeid: identificativo del nodo
    :param int t_nodetype: identificativo del tipo di nodo
    :return options: tupla con impostazioni del nodo
    :rtype: tuple
    """
    # le opzioni ottenute di default sono None
    options = None

    try:
        if t_nodetype == 0:
            # se il tipo di nodo e' 0, richiama funzione corretta
            options = get_options_type0(t_nodeid)
        else:
            # tipo di nodo non riconosciuto
            logger("WARNING: tipo nodo '{}' non conosciuto per ottenere le impostazioni".format(t_nodeid), logfile)

    except Exception as t_e:
        logger("ERROR: get_options(), errore sconosciuto sulla riga '{}': {}".format(sys.exc_info()[2].tb_lineno,
                                                                                     t_e),
               logfile)

    return options


def get_options_type0(t_nodeid):
    """
    Restituisce le impostazioni del nodo <t_nodeid> di tipo 0.

    Esegue l'istruzione SQL per restituire node_id e timebetweenread (tempo tra rilevazioni)
    del nodo <t_nodeid>.

    :param int t_nodeid: identificativo del nodo
    :return options: tupla con impostazioni del nodo
    :rtype: tuple
    """
    options = None

    try:
        query = "SELECT node_id, timebetweenread FROM t_type0_options WHERE node_id = %s"
        cursor.execute(query, [t_nodeid])
        options_data = cursor.fetchall()

        if len(options_data) == 1:
            options = "{'timeToWait': " + str(options_data[0][1]) + "}"
        else:
            logger("WARNING: numero opzioni del nodo '{}' errato".format(t_nodeid), logfile)

    except Exception as t_e:
        logger("ERROR: get_options_type0(), errore sconosciuto sulla riga '{}': {}".format(sys.exc_info()[2].tb_lineno,
                                                                                           t_e),
               logfile)

    return options


##################################################################################################################
#                                                                                                                #
#                                                 UTILS FUNCTIONS                                                #
#                                                                                                                #
##################################################################################################################


def valid_mac(t_mac):
    """
    Verifica validita' del mac address <t_mac>.

    Se la regular expression restituisce un match,
    l'indirizzo MAC e' valido: verra' restituito True.
    Se non e' presente il match, viene restituito False

    :param string t_mac: stringa, indirizzo MAC da validare
    :return valid: booleano che indica validita' di <t_mac>
    :rtype: bool
    """
    # non valido di default
    valid = False

    # verifica se <t_mac> (lower per rendere lettere minuscole) e' nel formato ??:??:??:??:??:??
    # (dove ? e' carattere con valore esadecimale)
    match = re.match("[0-9a-f]{2}([-:]?)[0-9a-f]{2}(\\1[0-9a-f]{2}){4}$", t_mac.lower())

    # esiste corrispondenza, il mac address e' valido
    if match:
        valid = True

    return valid


####################
#
# DATABASE FUNCTIONS
#
####################


def mysql_conn(t_configfile):
    """
    Si connette al database e restituisce oggetto connessione.

    Si assicura che il file di configurazione esiste e contiene le proprieta'
    necessarie a connettersi al DB.

    :param str t_configfile: stringa, percorso del file con credenziali per mysql
    :return mydb: oggetto connessione
    """

    if not os.path.isfile(t_configfile):
        raise Exception("Il file di configurazione '{}' non esiste".format(t_configfile))

    config = configparser.ConfigParser()
    config.read(t_configfile)

    # assicurati presenza delle sezioni nella configurazione
    if "Database" not in config:
        raise Exception("Sezione 'Database' non presente nel file configurazione")

    # assicurati che username, password, host e database di MySQL siano presenti nella configurazione
    if "username" not in config["Database"]:
        raise Exception("'username' non presente nella sezione 'Database' della configurazione")

    if "password" not in config["Database"]:
        raise Exception("'password' non presente nella sezione 'Database' della configurazione")

    if "host" not in config["Database"]:
        raise Exception("'host' non presente nella sezione 'Database' della configurazione")

    if "database" not in config["Database"]:
        raise Exception("'database' non presente nella sezione 'Database' della configurazione")

    mydb = mysql.connector.connect(
        host=config["Database"]["host"],
        user=config["Database"]["username"],
        passwd=config["Database"]["password"],
        database=config["Database"]["database"]
    )

    return mydb


def get_node(t_macaddr):
    """
    Restituisce id, ip, type_id del nodo con indirizzo MAC <t_macaddr>.

    La funzione esegue un'istruzione SQL di select per selezionare
    id, ip, type_id del nodo dalla tabella t_nodi dove (WHERE) mac corrisponde a <t_macaddr>.

    :param string t_macaddr: stringa con indirizzo MAC
    :return node: tupla con informazioni relative al nodo
    :rtype: tuple
    """
    logger("Ottengo informazioni sul node '{}'".format(t_macaddr), logfile)

    # seleziona id, ip, type_id dalla tabella t_nodi dove mac = <t_macaddr>
    query = "SELECT t_nodi.id, t_nodi.ip, t_nodi.type_id FROM t_nodi WHERE t_nodi.mac = %s"
    cursor.execute(query, [t_macaddr])

    # recupera dati dall'esecuzione dell'istruzione SQL
    node = cursor.fetchall()

    return node


def get_type(t_typeid):
    """
    Restituisce id, description, category_id del nodo con type_id = <t_typeid>.

    La funzione esegue un'istruzione SQL di select per selezionare
    id, description, category_id dalla tabella t_types dove (WHERE) id = <t_typeid>

    :param int t_typeid: intero, identifica tipo di nodo
    :return nodetype: tupla, contiene id, description, category_id del tipo di nodo <t_typeid>
    :rtype: tuple
    """
    logger("Ottengo informazioni sul tipo dei node '{}'".format(t_typeid), logfile)

    # seleziona id, description, category_id dalla tabella t_types dove id = <t_typeid>
    query = "SELECT t_types.id, t_types.description, t_types.category_id FROM t_types WHERE t_types.id = %s"
    cursor.execute(query, [t_typeid])

    # recupera dati dall'esecuzione dell'istruzione SQL
    nodetype = cursor.fetchall()

    return nodetype


####################
#
# MQTT FUNCTIONS
#
####################


def mqtt_conn(t_configfile):
    """
    Si connette al broker MQTT e restituisce oggetto connessione.

    Si assicura che il file di configurazione esiste e contiene le proprieta'
    necessarie a connettersi al broker MQTT.

    :param str t_configfile: stringa, percorso del file con credenziali per mysql
    :return t_client: oggetto client
    """

    if not os.path.isfile(t_configfile):
        raise Exception("Il file di configurazione '{}' non esiste".format(t_configfile))

    config = configparser.ConfigParser()  # crea oggetto config
    config.read(t_configfile)             # leggi il file di configurazione

    # assicurati presenza delle sezioni nella configurazione
    if "MQTT broker" not in config:
        raise Exception("Sezione 'MQTT broker' non presente nel file configurazione")

    # assicurati che username, password, host e port del broker MQTT siano presenti nella configurazione
    if "username" not in config["MQTT broker"]:
        raise Exception("'username' non presente nella sezione 'MQTT broker' della configurazione")

    if "password" not in config["MQTT broker"]:
        raise Exception("'password' non presente nella sezione 'MQTT broker' della configurazione")

    if "host" not in config["MQTT broker"]:
        raise Exception("'host' non presente nella sezione 'MQTT broker' della configurazione")

    if "port" not in config["MQTT broker"]:
        raise Exception("'port' non presente nella sezione 'MQTT broker' della configurazione")

    # prepara il client alla connessione al broker MQTT (identificativo "mqtt_manager", sessione pulita)
    t_client = mqtt.Client(client_id="mqtt_manager", clean_session=True)

    # aggiungi callback per eventi
    t_client.on_connect = on_connect        # richiama on_connect() quando il client mqtt si connette
    t_client.on_message = on_message        # richiama quando il client riceve messaggi sui maintopic
    t_client.on_disconnect = on_disconnect  # richiama quando si disconnette il client

    # imposta username e password per connessione
    t_client.username_pw_set(username=config["MQTT broker"]["username"],
                             password=config["MQTT broker"]["password"])

    logger("Connessione al broker MQTT", logfile)

    # connettiti al broker mqtt con dominio/ip <host> e porta <port>
    t_client.connect(config["MQTT broker"]["host"],
                     int(config["MQTT broker"]["port"]),
                     60)

    return t_client


####################
#
# LOG FUNCTIONS
#
####################


def logger(t_message, t_logfile):
    """
    Scrive nel file di log <t_logfile> la riga <t_message>.

    La funzione ottiene il timestamp attuale e scrive direttamente
    su file senza aspettare la chiusura del file stesso.

    Il programma, essendo un loop infinito, dovrebbe
    terminare solo in situazioni anomale: questo
    significa che non si puo' attendere la chiusura del file
    per salvare i messaggi di log (andrebbero persi).

    :param string t_message: stringa, contiene messaggio di log da scrivere
    :param t_logfile: file di log (aperto) da scrivere
    """
    # ottieni timestamp
    ts = int(time.time())

    # visualizza messaggio se boold = True
    if boold:
        print("[{}] {}".format(ts, t_message))

    # scrivi il file subito
    t_logfile.write("[{}] {}\n".format(ts, t_message))
    t_logfile.flush()


if __name__ == "__main__":

    if boold:
        print("Start")

    # maintopic riconosciuti dal sistema
    maintopics = [{"name": "presentation", "function": manage_presentation},  # gestisce presentazione nodi
                  {"name": "data", "function": manage_data}]                  # gestisce dati dei nodi

    # apri file di log
    logfile = open("log.txt", "a")

    try:
        logger("Connessione al database", logfile)
        
        # connettiti al database e richiedi cursore con prepared statements
        conn = mysql_conn(configfile_path)
        cursor = conn.cursor(prepared=True)

        # connettiti al broker MQTT e mantieni la connessione
        client = mqtt_conn(configfile_path)
        client.loop_forever()

    except mysql.connector.Error as e:
        # errore di mysql
        logger("ERROR: errore mysql sulla riga '{}': '{}'".format(sys.exc_info()[2].tb_lineno, e), logfile)

    except Exception as e:
        # errore non previsto
        logger("ERROR: errore sconosciuto sulla riga '{}': '{}'".format(sys.exc_info()[2].tb_lineno, e), logfile)
    finally:
        # a termine del try/except (in teoria mai) disconnettiti dal DB
        if conn is not None and conn.is_connected():
            cursor.close()
            conn.close()
            logger("Connessione al DB chiusa", logfile)

    # chiudi file di log
    logfile.close()
