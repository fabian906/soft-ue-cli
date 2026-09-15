"""Weldborn-specific live PIE command families."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from typing import Any

from .host_input import (
    HostInputError,
    dispatch_click,
    geometry_to_screen,
    screen_to_viewport,
)


class WeldbornCommandError(RuntimeError):
    """A Weldborn command contract was not satisfied."""


WELDBORN_TOOL_COMMANDS: dict[str, str] = {
    "weldborn.input.geometry": "input world",
    "weldborn.input.widget_geometry": "input widget",
    "weldborn.wait.frames": "wait",
    "weldborn.palette.list": "palette list",
    "weldborn.palette.select": "palette select",
    "weldborn.authoring.snapshot": "authoring snapshot",
    "weldborn.authoring.cancel": "authoring cancel",
    "weldborn.authoring.bay_reset": "authoring bay-reset",
    "weldborn.authoring.select_port": "authoring select-port",
    "weldborn.authoring.layout": "authoring layout",
    "weldborn.startup.snapshot": "startup snapshot",
    "weldborn.startup.skip": "startup skip",
    "weldborn.startup.new_game": "startup new-game",
    "weldborn.communication.snapshot": "communication snapshot",
    "weldborn.communication.advance": "communication advance",
    "weldborn.communication.choose": "communication choose",
    "weldborn.contract.snapshot": "contract snapshot",
    "weldborn.contract.accept": "contract accept",
    "weldborn.world.snapshot": "world snapshot",
    "weldborn.placement.confirm": "placement confirm",
    "weldborn.factory_design.begin": "factory-design begin",
    "weldborn.factory_design.rectangle": "factory-design rectangle",
    "weldborn.factory_design.save": "factory-design save",
    "weldborn.step.creator.status": "step creator status",
    "weldborn.step.creator.open": "step creator open",
    "weldborn.step.creator.close": "step creator close",
    "weldborn.step.creator.run_import": "step creator run-import",
    "weldborn.step.creator.inspect_session": "step creator inspect-session",
    "weldborn.step.creator.apply_session": "step creator apply-session",
    "weldborn.step.creator.clear_preview": "step creator clear-preview",
}


def build_log_since_arguments(
    cursor: str,
    *,
    categories: Sequence[str] | None = None,
) -> dict[str, object]:
    normalized_cursor = cursor.strip()
    if not normalized_cursor:
        raise WeldbornCommandError("log since requires a non-empty cursor")
    arguments: dict[str, object] = {"lines": 0, "since": normalized_cursor}
    if categories:
        arguments["category"] = list(dict.fromkeys(categories))
    return arguments


def _vector(value: str, length: int, flag: str) -> list[float]:
    parts = value.split(",")
    if len(parts) != length:
        raise WeldbornCommandError(f"{flag} requires {length} comma-separated numbers")
    try:
        return [float(part) for part in parts]
    except ValueError as exc:
        raise WeldbornCommandError(f"{flag} requires numeric values") from exc


def _pair(value: object, field: str) -> tuple[float, float]:
    if not isinstance(value, list) or len(value) != 2:
        raise WeldbornCommandError(f"bridge response field '{field}' must contain two numbers")
    try:
        return float(value[0]), float(value[1])
    except (TypeError, ValueError) as exc:
        raise WeldbornCommandError(f"bridge response field '{field}' must contain two numbers") from exc


def _bridge_call(tool_name: str, arguments: dict[str, object]) -> dict[str, Any]:
    from . import __main__ as main_mod

    return main_mod._run_tool(tool_name, arguments)


def _print_json(payload: object) -> None:
    from . import __main__ as main_mod

    main_mod._print_json(payload)


def _run_and_print(tool_name: str, arguments: dict[str, object]) -> None:
    _print_json(_bridge_call(tool_name, arguments))


def cmd_input_click(args: argparse.Namespace) -> None:
    point = _vector(args.at, 2, "--at")
    try:
        _print_json(dispatch_click((point[0], point[1]), button=args.button))
    except HostInputError as exc:
        raise WeldbornCommandError(str(exc)) from exc


def cmd_input_world(args: argparse.Namespace) -> None:
    position = _vector(args.pos, 3, "--pos")
    geometry = _bridge_call("weldborn.input.geometry", {"world": "pie", "pos": position})
    projected = _pair(geometry.get("projected_viewport_px"), "projected_viewport_px")
    origin = _pair(geometry.get("pie_viewport_origin_abs"), "pie_viewport_origin_abs")
    scale = float(geometry.get("slate_dpi_scale", 0.0))
    screen = geometry_to_screen(projected, geometry)
    round_trip = screen_to_viewport(screen, origin, scale)
    if abs(round_trip[0] - projected[0]) > 0.01 or abs(round_trip[1] - projected[1]) > 0.01:
        raise WeldbornCommandError("world projection failed the viewport round trip")
    try:
        input_result = dispatch_click(screen, button=args.button)
    except HostInputError as exc:
        raise WeldbornCommandError(str(exc)) from exc
    _print_json({"geometry": geometry, "input": input_result})


def cmd_input_widget(args: argparse.Namespace) -> None:
    geometry = _bridge_call(
        "weldborn.input.widget_geometry",
        {"world": "pie", "path": args.path},
    )
    screen = _pair(geometry.get("screen_center_abs"), "screen_center_abs")
    try:
        input_result = dispatch_click(screen, button=args.button)
    except HostInputError as exc:
        raise WeldbornCommandError(str(exc)) from exc
    _print_json({"geometry": geometry, "input": input_result})


def cmd_wait_frames(args: argparse.Namespace) -> None:
    if args.game < 0 or args.slate < 0:
        raise WeldbornCommandError("wait counts must be non-negative")
    responses = [
        _bridge_call("weldborn.wait.frames", {})
        for _ in range(max(args.game, args.slate))
    ]
    _print_json(
        {
            "ok": True,
            "game_ticks": args.game,
            "slate_ticks": args.slate,
            "dispatches": len(responses),
            "last": responses[-1] if responses else None,
        }
    )


def cmd_palette_list(args: argparse.Namespace) -> None:
    _run_and_print("weldborn.palette.list", {"world": "pie"})


def cmd_palette_select(args: argparse.Namespace) -> None:
    result = _bridge_call(
        "weldborn.palette.select",
        {"world": "pie", "content_id": args.content_id},
    )
    if result.get("ok"):
        result["settled_frame"] = _bridge_call("weldborn.wait.frames", {})
        result["settled_snapshot"] = _bridge_call(
            "weldborn.authoring.snapshot", {"world": "pie"}
        )
    _print_json(result)


def cmd_authoring_snapshot(args: argparse.Namespace) -> None:
    _run_and_print("weldborn.authoring.snapshot", {"world": "pie"})


def cmd_authoring_cancel(args: argparse.Namespace) -> None:
    _run_and_print("weldborn.authoring.cancel", {"world": "pie"})


def cmd_authoring_bay_reset(args: argparse.Namespace) -> None:
    _run_and_print("weldborn.authoring.bay_reset", {"world": "pie"})


def cmd_authoring_select_port(args: argparse.Namespace) -> None:
    arguments: dict[str, object] = {"world": "pie", "port_id": args.port_id}
    if args.placement_id:
        arguments["placement_id"] = args.placement_id
    _run_and_print("weldborn.authoring.select_port", arguments)


def cmd_authoring_layout(args: argparse.Namespace) -> None:
    arguments: dict[str, object] = {"world": "pie", "content_id": args.content_id}
    if args.facing is not None:
        arguments["facing"] = args.facing
    _run_and_print("weldborn.authoring.layout", arguments)


def cmd_log_bookmark(args: argparse.Namespace) -> None:
    result = _bridge_call("get-logs", {"lines": 0})
    cursor = str(result.get("next_cursor", "")).strip()
    if not cursor:
        raise WeldbornCommandError("get-logs did not return a bookmark cursor")
    _print_json({"cursor": cursor})


def cmd_log_since(args: argparse.Namespace) -> None:
    _run_and_print(
        "get-logs",
        build_log_since_arguments(args.cursor, categories=args.category),
    )


def _with_world(arguments: dict[str, object]) -> dict[str, object]:
    return {"world": "pie", **arguments}


def _startup_new_game_args(args: argparse.Namespace) -> dict[str, object]:
    return _with_world({"profile_id": args.profile_id, "seed": args.seed})


def _communication_target_args(args: argparse.Namespace) -> dict[str, object]:
    return _with_world(
        {"channel": args.channel, "communication_id": args.communication_id}
    )


def _communication_choose_args(args: argparse.Namespace) -> dict[str, object]:
    arguments = _communication_target_args(args)
    arguments["choice_index"] = args.choice_index
    return arguments


def _contract_accept_args(args: argparse.Namespace) -> dict[str, object]:
    return _with_world({"contract_id": args.contract_id})


def _world_snapshot_args(args: argparse.Namespace) -> dict[str, object]:
    arguments: dict[str, object] = _with_world({})
    if args.after_event_id:
        arguments["after_event_id"] = args.after_event_id
    if args.placement_id:
        arguments["placement_id"] = args.placement_id
    if args.runtime_factory_id:
        arguments["runtime_factory_id"] = args.runtime_factory_id
    return arguments


def _placement_confirm_args(args: argparse.Namespace) -> dict[str, object]:
    return _with_world({"x": args.x, "y": args.y})


def _factory_design_rectangle_args(
    args: argparse.Namespace,
) -> dict[str, object]:
    return _with_world(
        {
            "min_x": args.min_x,
            "min_y": args.min_y,
            "max_x": args.max_x,
            "max_y": args.max_y,
        }
    )


def _step_handler(tool_name: str, argument_builder: Callable[[argparse.Namespace], dict[str, object]] | None = None):
    def handler(args: argparse.Namespace) -> None:
        arguments = argument_builder(args) if argument_builder else {}
        _run_and_print(tool_name, arguments)

    return handler


def _add_button(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--button", choices=("left", "right"), default="left")


def add_weldborn_command_parsers(sub: argparse._SubParsersAction) -> None:
    input_parser = sub.add_parser("input", help="Send guarded OS input to the Weldborn PIE preview.")
    input_sub = input_parser.add_subparsers(dest="input_action", required=True)
    click = input_sub.add_parser("click", help="Click one absolute desktop point after HWND validation.")
    click.add_argument("--at", required=True, metavar="X,Y")
    _add_button(click)
    click.set_defaults(func=cmd_input_click)
    world = input_sub.add_parser("world", help="Project one world point and click its DPI-correct desktop point.")
    world.add_argument("--pos", required=True, metavar="X,Y,Z")
    _add_button(world)
    world.set_defaults(func=cmd_input_world)
    widget = input_sub.add_parser("widget", help="Resolve one UMG or Slate widget and click its center.")
    widget.add_argument("--path", required=True)
    _add_button(widget)
    widget.set_defaults(func=cmd_input_widget)

    wait = sub.add_parser("wait", help="Wait for game and Slate ticks before a dependent read.")
    wait.add_argument("--game", type=int, default=1, metavar="N")
    wait.add_argument("--slate", type=int, default=1, metavar="N")
    wait.set_defaults(func=cmd_wait_frames)

    palette = sub.add_parser("palette", help="Read or select Weldborn palette backing-model rows.")
    palette_sub = palette.add_subparsers(dest="palette_action", required=True)
    palette_list = palette_sub.add_parser("list", help="List all backing-model palette rows.")
    palette_list.set_defaults(func=cmd_palette_list)
    palette_select = palette_sub.add_parser("select", help="Select one content id through the production controller API.")
    palette_select.add_argument("content_id")
    palette_select.set_defaults(func=cmd_palette_select)

    authoring = sub.add_parser("authoring", help="Read or mutate typed Weldborn authoring state.")
    authoring_sub = authoring.add_subparsers(dest="authoring_action", required=True)
    snapshot = authoring_sub.add_parser("snapshot", help="Read one game-thread authoring snapshot.")
    snapshot.set_defaults(func=cmd_authoring_snapshot)
    cancel = authoring_sub.add_parser("cancel", help="Cancel the active authoring interaction or refuse when idle.")
    cancel.set_defaults(func=cmd_authoring_cancel)
    bay_reset = authoring_sub.add_parser("bay-reset", help="Run the production Bay reset command.")
    bay_reset.set_defaults(func=cmd_authoring_bay_reset)
    select_port = authoring_sub.add_parser("select-port", help="Select one visible current-layer port.")
    select_port.add_argument("port_id")
    select_port.add_argument("--placement-id")
    select_port.set_defaults(func=cmd_authoring_select_port)
    layout = authoring_sub.add_parser("layout", help="Resolve a content footprint, ports, facing, and Bay conflicts.")
    layout.add_argument("content_id")
    layout.add_argument("--facing", type=int, choices=range(4))
    layout.set_defaults(func=cmd_authoring_layout)

    log = sub.add_parser("log", help="Bookmark and read only later Weldborn diagnostic lines.")
    log_sub = log.add_subparsers(dest="log_action", required=True)
    bookmark = log_sub.add_parser("bookmark", help="Return the current bridge log cursor.")
    bookmark.set_defaults(func=cmd_log_bookmark)
    since = log_sub.add_parser("since", help="Read only lines after a required cursor.")
    since.add_argument("cursor")
    since.add_argument(
        "--category",
        action="append",
        choices=("authoring", "sim", "objective"),
        default=[],
    )
    since.set_defaults(func=cmd_log_since)

    step = sub.add_parser("step", help="Call Weldborn STEP Creator bridge tools.")
    step_sub = step.add_subparsers(dest="step_action", required=True)
    creator = step_sub.add_parser("creator", help="Control the Weldborn STEP Creator bridge integration.")
    creator_sub = creator.add_subparsers(dest="step_creator_action", required=True)
    step_specs = {
        "status": ("weldborn.step.creator.status", None),
        "open": ("weldborn.step.creator.open", lambda args: {"step_path": args.step_path} if args.step_path else {}),
        "close": ("weldborn.step.creator.close", None),
        "run-import": ("weldborn.step.creator.run_import", lambda args: {"step_path": args.step_path}),
        "inspect-session": ("weldborn.step.creator.inspect_session", None),
        "apply-session": ("weldborn.step.creator.apply_session", None),
        "clear-preview": ("weldborn.step.creator.clear_preview", None),
    }
    for name, (tool_name, builder) in step_specs.items():
        command = creator_sub.add_parser(name, help=f"Call {tool_name}.")
        if name == "open":
            command.add_argument("--step-path")
        elif name == "run-import":
            command.add_argument("step_path")
        command.set_defaults(func=_step_handler(tool_name, builder))

    startup = sub.add_parser("startup", help="Read and drive Weldborn startup readiness.")
    startup_sub = startup.add_subparsers(dest="startup_action", required=True)
    startup_snapshot = startup_sub.add_parser("snapshot", help="Call weldborn.startup.snapshot.")
    startup_snapshot.set_defaults(func=_step_handler("weldborn.startup.snapshot", lambda args: _with_world({})))
    startup_skip = startup_sub.add_parser("skip", help="Call weldborn.startup.skip.")
    startup_skip.set_defaults(func=_step_handler("weldborn.startup.skip", lambda args: _with_world({})))
    startup_new_game = startup_sub.add_parser("new-game", help="Call weldborn.startup.new_game with an explicit profile and seed.")
    startup_new_game.add_argument("--profile-id", required=True)
    startup_new_game.add_argument("--seed", type=int, required=True)
    startup_new_game.set_defaults(func=_step_handler("weldborn.startup.new_game", _startup_new_game_args))

    communication = sub.add_parser("communication", help="Read and drive Weldborn dialogue and system-message channels.")
    communication_sub = communication.add_subparsers(dest="communication_action", required=True)
    communication_snapshot = communication_sub.add_parser("snapshot", help="Call weldborn.communication.snapshot.")
    communication_snapshot.set_defaults(func=_step_handler("weldborn.communication.snapshot", lambda args: _with_world({})))
    communication_advance = communication_sub.add_parser("advance", help="Call weldborn.communication.advance after the same-id check.")
    communication_advance.add_argument("--channel", required=True, choices=("dialogue", "system-message"))
    communication_advance.add_argument("--communication-id", required=True)
    communication_advance.set_defaults(func=_step_handler("weldborn.communication.advance", _communication_target_args))
    communication_choose = communication_sub.add_parser("choose", help="Call weldborn.communication.choose with one offered index.")
    communication_choose.add_argument("--channel", required=True, choices=("dialogue", "system-message"))
    communication_choose.add_argument("--communication-id", required=True)
    communication_choose.add_argument("--choice-index", type=int, required=True)
    communication_choose.set_defaults(func=_step_handler("weldborn.communication.choose", _communication_choose_args))

    contract = sub.add_parser("contract", help="Read and accept Weldborn assignment contracts.")
    contract_sub = contract.add_subparsers(dest="contract_action", required=True)
    contract_snapshot = contract_sub.add_parser("snapshot", help="Call weldborn.contract.snapshot.")
    contract_snapshot.set_defaults(func=_step_handler("weldborn.contract.snapshot", lambda args: _with_world({})))
    contract_accept = contract_sub.add_parser("accept", help="Call weldborn.contract.accept by runtime GUID.")
    contract_accept.add_argument("--contract-id", required=True)
    contract_accept.set_defaults(func=_step_handler("weldborn.contract.accept", _contract_accept_args))

    world = sub.add_parser("world", help="Read compact Weldborn World authoring state and new structured events.")
    world_sub = world.add_subparsers(dest="world_action", required=True)
    world_snapshot = world_sub.add_parser("snapshot", help="Call weldborn.world.snapshot with an optional event baseline.")
    world_snapshot.add_argument("--after-event-id")
    world_snapshot.add_argument("--placement-id")
    world_snapshot.add_argument("--runtime-factory-id")
    world_snapshot.set_defaults(func=_step_handler("weldborn.world.snapshot", _world_snapshot_args))

    placement = sub.add_parser("placement", help="Confirm the active Weldborn placement at exact World coordinates.")
    placement_sub = placement.add_subparsers(dest="placement_action", required=True)
    placement_confirm = placement_sub.add_parser("confirm", help="Call weldborn.placement.confirm.")
    placement_confirm.add_argument("--x", type=int, required=True)
    placement_confirm.add_argument("--y", type=int, required=True)
    placement_confirm.set_defaults(func=_step_handler("weldborn.placement.confirm", _placement_confirm_args))

    factory_design = sub.add_parser("factory-design", help="Drive the Weldborn World Factory design workflow.")
    factory_design_sub = factory_design.add_subparsers(dest="factory_design_action", required=True)
    factory_design_begin = factory_design_sub.add_parser("begin", help="Call weldborn.factory_design.begin.")
    factory_design_begin.set_defaults(func=_step_handler("weldborn.factory_design.begin", lambda args: _with_world({})))
    factory_design_rectangle = factory_design_sub.add_parser("rectangle", help="Call weldborn.factory_design.rectangle with inclusive bounds.")
    factory_design_rectangle.add_argument("--min-x", type=int, required=True)
    factory_design_rectangle.add_argument("--min-y", type=int, required=True)
    factory_design_rectangle.add_argument("--max-x", type=int, required=True)
    factory_design_rectangle.add_argument("--max-y", type=int, required=True)
    factory_design_rectangle.set_defaults(func=_step_handler("weldborn.factory_design.rectangle", _factory_design_rectangle_args))
    factory_design_save = factory_design_sub.add_parser("save", help="Call weldborn.factory_design.save.")
    factory_design_save.set_defaults(func=_step_handler("weldborn.factory_design.save", lambda args: _with_world({})))
