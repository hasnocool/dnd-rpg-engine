# adapters/godot3d/RPGActor3D.gd
# Binds authoritative entity coordinates/state to a Node3D presentation.
class_name RPGActor3D
extends Node3D

@export var entity_id := ""
@export var interpolation_speed := 8.0
var _target := Vector3.ZERO
var _alive := true

func _ready() -> void:
    _target = position

func _process(delta: float) -> void:
    position = position.lerp(_target, min(1.0, interpolation_speed * delta))
    visible = _alive

func apply_entity_state(entity: Dictionary) -> void:
    if str(entity.get("id", "")) != entity_id:
        return
    var p: Dictionary = entity.get("position", {})
    _target = Vector3(float(p.get("x", 0.0)), float(p.get("z", 0.0)), float(p.get("y", 0.0)))
    _alive = bool(entity.get("alive", true))

func apply_engine_event(event: Dictionary) -> void:
    var type := str(event.get("type", ""))
    if type == "entity.moved" and str(event.get("actor_id", "")) == entity_id:
        var p: Dictionary = event.get("payload", {}).get("to", {})
        _target = Vector3(float(p.get("x", 0.0)), float(p.get("z", 0.0)), float(p.get("y", 0.0)))
    elif type == "combat.entity_defeated" and str(event.get("target_id", "")) == entity_id:
        _alive = false
