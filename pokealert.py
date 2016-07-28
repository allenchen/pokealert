#!/usr/bin/python3

import urllib3
import json
import pokemon_lib
import pokealert_config
import time
import smtplib
import logging
from email.mime.text import MIMEText
from twisted.internet import task
from twisted.internet import reactor

def make_pokevision_request(pool, request_type, lon, lat):
  response = pool.request('GET', 'https://pokevision.com/map/{}/{}/{}'.format(request_type, lon, lat))
  return json.loads(response.data.decode('utf-8'))

def send_pokealert_email(smtp, from_email, to_email, body):
  body = '\n' + body # needs newline between header and body
  smtp.sendmail(from_email, to_email, body)

def loop(from_email, to_email, coordinates, smtp, request_pool, seen_uids, alert_pokemon, exclude_pokemon):
  decoded_response = make_pokevision_request(request_pool, 'scan', coordinates[0], coordinates[1])

  if (decoded_response['status'] == 'success'):
    job_id = decoded_response['jobId']
    decoded_pokemon_data = make_pokevision_request(request_pool, 'data', coordinates[0], coordinates[1])

    if (decoded_pokemon_data['status'] == 'success'):
      found_alertable_pokemon = False
      alertable_pokemon_messages = []
      for pokemon_data in decoded_pokemon_data['pokemon']:
        name = pokemon_lib.pokemon_name_from_id(pokemon_data['pokemonId'])
        ttl = int(round(pokemon_data['expiration_time'] - time.time()))
        if name not in exclude_pokemon:
          alertable_pokemon_messages += [name + " | TTL: " + str(ttl) + "s"]
          logging.info("Saw: " + name)
        if name in alert_pokemon:
          if pokemon_data['uid'] not in seen_uids:
            alertable_pokemon_messages += [name + " | TTL: " + str(ttl) + "s"]
            found_alertable_pokemon = True
            seen_uids.add(pokemon_data['uid'])
            logging.info("!!! Alert Fired: " + name)
          else:
            logging.info("Already seen uid: " + pokemon_data['uid'] + " (" + name + ")")

      if found_alertable_pokemon:
        message = '\n'.join(alertable_pokemon_messages)
        send_pokealert_email(smtp, from_email, to_email, message)
        logging.info(message)
        logging.info("----")
    else:
      logging.info('Request to fetch Pokemon data unsuccessful: ' + decoded_pokemon_data)
  else:
    logging.info('Request to scan unsuccessful: ' + decoded_response)

if __name__ == '__main__':
  smtp = smtplib.SMTP('smtp.gmail.com', 587)
  smtp.starttls()
  smtp.login(pokealert_config.gmail_smtp_username, pokealert_config.gmail_smtp_password)
  
  request_pool = urllib3.PoolManager()

  timeout = 120.0

  seen_uids = set()

  logging.basicConfig(filename="/pokealert.log", level=logging.INFO)

  scheduled_task = task.LoopingCall(
    loop,
    pokealert_config.from_email,
    pokealert_config.to_email,
    pokealert_config.coordinates, 
    smtp,
    request_pool,
    seen_uids,
    pokealert_config.alert_pokemon,
    pokealert_config.exclude_pokemon)

  scheduled_task.start(timeout)

  reactor.run()
