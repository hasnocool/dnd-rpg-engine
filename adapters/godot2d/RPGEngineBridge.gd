# adapters/godot2d/RPGEngineBridge.gd
# Godot 4.7.x adapter: transport-only bridge to the authoritative RPG engine.
class_name RPGEngineBridge2D
extends Node

signal event_received(event: Dictionary)
signal state_received(state: Dictionary)
signal command_ack(payload: Dictionary)
signal connection_error(message: String)

@export var api_base := "http://127.0.0.1:8000"
@export var ws_base := "ws://127.0.0.1:8000"

var campaign_id: String = ""
var _socket := WebSocketPeer.new()
var _connected := false

func connect_campaign(id: String) -> void:
    campaign_id = id
    var error := _socket.connect_to_url("%s/api/v1/campaigns/%s/ws" % [ws_base, campaign_id])
    if error != OK:
        connection_error.emit("WebSocket connection failed: %s" % error)
        return
    set_process(true)

func _process(_delta: float) -> void:
    if campaign_id.is_empty():
        return
    _socket.poll()
    var state := _socket.get_ready_state()
    if state == WebSocketPeer.STATE_OPEN:
        _connected = true
        while _socket.get_available_packet_count() > 0:
            var raw := _socket.get_packet().get_string_from_utf8()
            var parsed = JSON.parse_string(raw)
            if typeof(parsed) != TYPE_DICTIONARY:
                continue
            _handle_message(parsed)
    elif state == WebSocketPeer.STATE_CLOSED and _connected:
        _connected = false
        connection_error.emit("WebSocket closed")

func send_command(command: Dictionary, narrate := false) -> void:
    if _socket.get_ready_state() != WebSocketPeer.STATE_OPEN:
        connection_error.emit("WebSocket is not connected")
        return
    var envelope := {
        "kind": "command",
        "request_id": str(Time.get_ticks_usec()),
        "command": command,
        "narrate": narrate,
    }
    _socket.send_text(JSON.stringify(envelope))

func request_state() -> void:
    if _socket.get_ready_state() == WebSocketPeer.STATE_OPEN:
        _socket.send_text(JSON.stringify({"kind": "state"}))

func _handle_message(message: Dictionary) -> void:
    match message.get("kind", ""):
        "event":
            event_received.emit(message.get("event", {}))
        "state":
            state_received.emit(message.get("state", {}))
        "ack":
            command_ack.emit(message)
        "error":
            connection_error.emit(str(message.get("detail", "Unknown engine error")))
