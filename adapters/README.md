# Godot adapters

The bundled adapters target the current stable Godot 4.7 line. They keep Godot as a presentation/input client only: authoritative rules and timing stay in the server.

- `godot2d/RPGEngineBridge.gd` connects to the campaign WebSocket and emits engine events.
- `godot2d/RPGActor2D.gd` maps authoritative coordinates and entity state into `Node2D` presentation.
- `godot3d/RPGEngineBridge.gd` provides the same transport for 3D games.
- `godot3d/RPGActor3D.gd` maps authoritative state into `Node3D` presentation.
- `bindings/` maps logical entity/area/event IDs to local Godot scenes and presentation callbacks.

The adapter intentionally does not calculate rules, hit results, health, timing, or AI locally. Send commands to the engine and animate the returned events.
