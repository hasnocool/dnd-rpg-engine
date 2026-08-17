# adapters/godot2d/RPGActor2D.gd
# Binds one authoritative entity to a Node2D presentation.
class_name RPGActor2D
extends Node2D

@export var entity_id := ""
@export var units_to_pixels := 64.0
@export var interpolation_speed := 10.0

var _target_position := Vector2.ZERO
var _alive := true

func _ready() -> void:
    _target_position = position

func _process(delta: float) -> void:
    position = position.lerp(_target_position, min(1.0, interpolation_speed * delta))
    visible = _alive

func apply_entity_state(entity: Dictionary) -> void:
    if str(entity.get("id", "")) != entity_id:
        return
    var p: Dictionary = entity.get("position", {})
    _target_position = Vector2(float(p.get("x", 0.0)), float(p.get("y", 0.0))) * units_to_pixels
    _alive = bool(entity.get("alive", true))

func apply_engine_event(event: Dictionary) -> void:
    var actor := str(event.get("actor_id", ""))
    var target := str(event.get("target_id", ""))
    var type := str(event.get("type", ""))
    if type == "entity.moved" and actor == entity_id:
        var destination: Dictionary = event.get("payload", {}).get("to", {})
        _target_position = Vector2(float(destination.get("x", 0.0)), float(destination.get("y", 0.0))) * units_to_pixels
    elif type == "combat.entity_defeated" and target == entity_id:
        _alive = false
