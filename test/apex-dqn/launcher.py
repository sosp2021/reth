import asyncio

import asyncssh

WORKER_ENDPOINTS = ["10.0.0.1:234"]
TRAINER_ENDPOINT = "10.0.0.2:345"
PERWEZ_PORT = 2333
RB_PORTS = [2334, 2335, 2336, 2337]
RB_PORTS = [str(port) for port in RB_PORTS]


WORKER_COMMAND = "python ~/reth/test/apex-dqn/worker.py -r {} -s {} -p {} -rb {}"

TRAINER_COMMAND = "python ~/reth/test/apex-dqn/trainer.py -p {} -rb {}"

QUEUE = asyncio.Queue()


async def printer():
    while True:
        line = await QUEUE.get()
        print(line, end="")


async def handle_output(prefix, stream):
    async for line in stream:
        if len(line) == 0:
            continue
        await QUEUE.put(f"{prefix} {line}")


def parse_endpoint(ep):
    if ":" not in ep:
        host = ep
        port = 22
    else:
        host, port = ep.split(":")
    if "@" not in host:
        user = "root"
        addr = host
    else:
        user, addr = host.split("@")
    return user, addr, port


async def run(name, ep, command):
    user, addr, port = parse_endpoint(ep)
    async with asyncssh.connect(
        addr, username=user, port=int(port), known_hosts=None
    ) as conn:
        async with conn.create_process(command) as proc:
            await asyncio.gather(
                handle_output(f"[{name}][stdout]", proc.stdout),
                handle_output(f"[{name}][stderr]", proc.stderr),
            )


async def main_async():
    _, addr, _ = parse_endpoint(TRAINER_ENDPOINT)
    tasks = []
    tasks.append(
        run(
            "trainer",
            TRAINER_ENDPOINT,
            TRAINER_COMMAND.format(PERWEZ_PORT, " ".join(RB_PORTS)),
        )
    )
    for i, ep in enumerate(WORKER_ENDPOINTS):
        tasks.append(
            run(
                f"worker-node{i}",
                ep,
                WORKER_COMMAND.format(
                    i,
                    len(WORKER_ENDPOINTS),
                    f"http://{addr}:{PERWEZ_PORT}",
                    " ".join([f"tcp://{addr}:{port}" for port in RB_PORTS]),
                ),
            )
        )
    done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
    for fut in done:
        fut.result()


def main():
    loop = asyncio.get_event_loop()
    p_task = loop.create_task(printer())
    loop.run_until_complete(main_async())
    p_task.cancel()


if __name__ == "__main__":
    main()
