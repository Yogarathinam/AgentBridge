from __future__ import annotations

import asyncio

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from app.protocol import error_response, ok_response


def create_server(runtime):
    app = FastAPI(title='AgentBridge')

    @app.get('/health')
    async def health():
        return {'status': 'ok', **runtime.state.get_status()}

    @app.websocket('/ws')
    async def websocket_endpoint(websocket: WebSocket):
        await runtime.connection_manager.connect(websocket)
        try:
            while True:
                data = await websocket.receive_json()
                msg_type = data.get('type')
                request_id = str(data.get('request_id') or '')
                print(f'[ws] recv type={msg_type} request_id={request_id}')

                if msg_type == 'ping':
                    await websocket.send_json(
                        ok_response('pong', request_id, {'app': 'AgentBridge'})
                    )

                elif msg_type == 'status':
                    await websocket.send_json(
                        ok_response('status_result', request_id, runtime.state.get_status())
                    )

                elif msg_type == 'ask':
                    prompt = str((data.get('payload') or {}).get('prompt') or '').strip()
                    if not prompt:
                        await websocket.send_json(
                            error_response(request_id, 'BAD_REQUEST', 'Prompt is empty.')
                        )
                        continue

                    timeout_sec = 60
                    runtime.state.update_status(busy=True, last_info='Processing request...')
                    try:
                        result = await asyncio.wait_for(
                            asyncio.get_running_loop().run_in_executor(
                                None,
                                lambda: runtime.gemini_loop.run(runtime.gemini_worker.ask(prompt)),
                            ),
                            timeout=timeout_sec,
                        )
                        await websocket.send_json(
                            ok_response('ask_result', request_id, result)
                        )
                    except asyncio.TimeoutError:
                        await websocket.send_json(
                            error_response(
                                request_id,
                                'TIMEOUT',
                                f'Request timed out after {timeout_sec} seconds.',
                            )
                        )
                    except RuntimeError as exc:
                        code = str(exc)
                        await websocket.send_json(
                            error_response(request_id, code, code.replace('_', ' ').title())
                        )
                    finally:
                        runtime.state.update_status(busy=False)

                elif msg_type == 'new_chat':
                    result = runtime.gemini_loop.run(runtime.gemini_worker.new_chat())
                    await websocket.send_json(
                        ok_response('new_chat_result', request_id, runtime.state.get_status())
                    )

                elif msg_type == 'login_check':
                    result = runtime.gemini_loop.run(runtime.gemini_worker.check_login())
                    await websocket.send_json(
                        ok_response(
                            'login_check_result',
                            request_id,
                            {'logged_in': result, **runtime.state.get_status()},
                        )
                    )

                elif msg_type == 'service_status':
                    await websocket.send_json(
                        ok_response('service_status_result', request_id, runtime.state.get_status())
                    )

                else:
                    await websocket.send_json(
                        error_response(
                            request_id,
                            'UNKNOWN_TYPE',
                            f'Unsupported type: {msg_type}',
                        )
                    )

        except WebSocketDisconnect:
            await runtime.connection_manager.disconnect(websocket)
            print('[ws] websocket disconnect')
        except Exception as exc:
            await runtime.connection_manager.disconnect(websocket)
            print(f'[ws] websocket error: {exc}')

    return app