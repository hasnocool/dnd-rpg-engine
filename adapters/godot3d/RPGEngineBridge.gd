# adapters/godot3d/RPGEngineBridge.gd
# Godot 4.7.x adapter: network bridge for 3D clients.
class_name RPGEngineBridge3D
extends Node

signal event_received(event: Dictionary)
signal state_received(state: Dictionary)
signal command_ack(payload: Dictionary)
signal connection_error(message: String)

@export var ws_base := "ws://127.0.0.1:8000"
var campaign_id := ""
var _socket := WebSocketPeer.new()
var _was_open := false

func connect_campaign(id: String) -> void:
    campaign_id = id
    var error := _socket.connect_to_url("%s/api/v1/campaigns/%s/ws" % [ws_base, id])
    if error != OK:
        connection_error.emit("WebSocket connection failed: %s" % error)

func _process(_delta: float) -> void:
    _socket.poll()
    var state := _socket.get_ready_state()
    if state == WebSocketPeer.STATE_OPEN:
        _was_open = true
        while _socket.get_available_packet_count() > 0:
            var parsed = JSON.parse_string(_socket.get_packet().get_string_from_utf8())
            if typeof(parsed) == TYPE_DICTIONARY:
                _route(parsed)
    elif state == WebSocketPeer.STATE_CLOSED and _was_open:
        _was_open = false
        connection_error.emit("WebSocket closed")

func send_command(command: Dictionary, narrate := false) -> void:
    if _socket.get_ready_state() != WebSocketPeer.STATE_OPEN:
        connection_error.emit("WebSocket is not connected")
        return
    _socket.send_text(JSON.stringify({
        "kind": "command",
        "request_id": str(Time.get_ticks_usec()),
        "command": command,
        "narrate": narrate,
    }))

func request_state() -> void:
    if _socket.get_ready_state() == WebSocketPeer.STATE_OPEN:
        _socket.send_text(JSON.stringify({"kind": "state"}))

func _route(message: Dictionary) -> void:
    match message.get("kind", ""):
        "event": event_received.emit(message.get("event", {}))
        "state": state_received.emit(message.get("state", {}))
        "ack": command_ack.emit(message)
        "error": connection_error.emit(str(message.get("detail", "Unknown engine error")))
