from enum import Enum
import random
import time
import numpy as np
from tqdm import trange
from pathlib import Path
from rich.progress import Progress
import typer
from esrgan_dream import ColorMode
from esrgan_dream import dream

from esrgan_dream.dream import Dream, DreamFromImage

MAX_SEED = 2**32 - 1

app = typer.Typer()


@app.command()
def run(
    experiment: Path = typer.Argument(..., help="Path to experiment file"),
    iterations: int = typer.Option(4, help="Number of upscaling iterations to run"),
    out: Path = typer.Option(Path("out"), help="Path to the output folder"),
):
    out.mkdir(exist_ok=True, parents=True)
    with experiment.open() as fp:
        dream = Dream.load(fp)
    with open(f"{out}/{dream.encoded_seed}.yml", "w") as fp:
        dream.dump(fp)
    with Progress() as progress:
        task = progress.add_task(
            f"Upscaling {experiment.name} (as {out}/{dream.encoded_seed}.yml)",
            total=iterations,
        )
        dream.dream(iterations, out, lambda: progress.advance(task))


@app.command()
def experiments(
    model_path: str = typer.Option(
        "weights/RealESRGAN_x4plus.pth", help="Path to the model file"
    ),
    out: Path = typer.Option(Path("out"), help="Path to the output folder"),
    iterations: int = typer.Option(3, help="Number of times to upscale the image"),
    experiments: int = typer.Option(1, help="Number of times to run the experiment"),
    color_mode: ColorMode = typer.Option(
        ColorMode.color, help="Number of color channels in the image"
    ),
    tile: int = typer.Option(512, help="Size for image tiles (0: no tiling)"),
    blur: int = typer.Option(3, help="Blur kernel size"),
    color_offset: int = typer.Option(
        0, help="Offset to make the image brighter or darker"
    ),
    initial_width: int = typer.Option(16, help="Initial width of the image"),
    initial_height: int = typer.Option(16, help="Initial height of the image"),
    comment: str = typer.Option(None, help="Comment to add to the output folder name"),
):
    out.mkdir(exist_ok=True, parents=True)
    numpy_seeds = [random.randint(0, MAX_SEED) for _ in range(experiments)]
    torch_seeds = [random.randint(0, MAX_SEED) for _ in range(experiments)]

    # setup experiments
    experiments = [
        Dream(
            numpy_seed,
            torch_seed,
            initial_width,
            initial_height,
            tile,
            color_mode,
            model_path,
            blur,
            color_offset,
        )
        for numpy_seed, torch_seed in zip(numpy_seeds, torch_seeds)
    ]

    start = time.time()
    with Progress() as progress:
        # setup progress tracking
        experiment_progress = [
            (
                experiment,
                progress.add_task(
                    f"Experiment {i} ({experiment.id})",
                    total=iterations,
                ),
            )
            for i, experiment in enumerate(experiments)
        ]
        # perform experiments
        for experiment, task in experiment_progress:
            with open(f"{out}/{experiment.id}.yml", "w") as fp:
                experiment.dump(fp)
            experiment.dream(iterations, out, lambda: progress.advance(task))
    stop = time.time()
    n = len(experiments)
    typer.secho(
        f"Finished {n} experiments in {stop - start:.2f} seconds ({(stop - start)/n:.2f} s/experiment))",
        fg=typer.colors.GREEN,
    )


@app.command()
def from_image(
    image_path: Path,
    out: Path = typer.Option(Path("out"), help="Path to the output folder"),
    model_path: str = typer.Option(
        "weights/RealESRGAN_x4plus.pth", help="Path to the model file"
    ),
    iterations: int = typer.Option(3, help="Number of times to upscale the image"),
    tile: int = typer.Option(512, help="Size for image tiles (0: no tiling)"),
):
    out.mkdir(exist_ok=True, parents=True)
    numpy_seed = random.randint(0, MAX_SEED)
    torch_seed = random.randint(0, MAX_SEED)

    if image_path.is_file():
        dreams = [DreamFromImage(image_path, numpy_seed, torch_seed, tile, model_path)]
    else:
        dreams = [
            DreamFromImage(image, numpy_seed, torch_seed, tile, model_path)
            for image in image_path.glob("*.png")
        ]

    with Progress() as progress:

        def tracking_task(dream):
            return progress.add_task(
                f"{dream.id}: Upscaling {dream.image_path.name}",
                total=iterations,
            )

        overall_progress = progress.add_task("[medium_purple1]Total progress", total=len(dreams) * iterations)
        tasks = [(dream, tracking_task(dream)) for dream in dreams]
        for dream, task in tasks:
            def update():
                progress.advance(overall_progress)
                progress.advance(task)
            dream.dream(iterations, out, update)

if __name__ == "__main__":
    app()
