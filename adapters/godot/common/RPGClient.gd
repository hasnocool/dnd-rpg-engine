class_name RPGClient
extends Node

signal command_ack(payload: Dictionary)
signal game_event(payload: Dictionary)
signal connection_state_changed(connected: bool)

var base_url: String = "http://127.0.0.1:8000"
var access_token: String = ""
var campaign_id: String = ""
var client_id: String = ""
var client_sequence: int = 1
var socket := WebSocketPeer.new()

func configure(url: String, token: String = "") -> void:
    base_url = url.trim_suffix("/")
    access_token = token

func connect_campaign(new_campaign_id: String, new_client_id: String) -> Error:
    campaign_id = new_campaign_id
    client_id = new_client_id
    var ws_url := base_url.replace("https://", "wss://").replace("http://", "ws://")
    ws_url += "/api/v1/reliable/campaigns/%s/ws?client_id=%s" % [campaign_id.uri_encode(), client_id.uri_encode()]
    if not access_token.is_empty():
        ws_url += "&access_token=" + access_token.uri_encode()
    var error := socket.connect_to_url(ws_url)
    if error == OK:
        set_process(true)
    return error

func send_command(command: Dictionary, narrate: bool = false) -> Error:
    if socket.get_ready_state() != WebSocketPeer.STATE_OPEN:
        return ERR_UNCONFIGURED
    var envelope := {
        "kind": "command",
        "client_id": client_id,
        "client_sequence": client_sequence,
        "command": command,
        "narrate": narrate,
    }
    return socket.send_text(JSON.stringify(envelope))

func _process(_delta: float) -> void:
    socket.poll()
    var state := socket.get_ready_state()
    if state == WebSocketPeer.STATE_OPEN:
        while socket.get_available_packet_count() > 0:
            var text := socket.get_packet().get_string_from_utf8()
            var payload = JSON.parse_string(text)
            if payload is Dictionary:
                if payload.get("kind") == "ack":
                    if not payload.get("duplicate", false):
                        client_sequence += 1
                    command_ack.emit(payload)
                elif payload.get("kind") == "event":
                    game_event.emit(payload.get("event", {}))
    elif state == WebSocketPeer.STATE_CLOSED:
        set_process(false)
        connection_state_changed.emit(false)
