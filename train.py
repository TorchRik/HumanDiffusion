import warnings

import hydra
import torch
from hydra.utils import instantiate
from omegaconf import OmegaConf
from torch.cuda.amp import GradScaler

from src.datasets.data_utils import get_dataloaders
from src.trainer.refl_trainer import ReFLTrainer
from src.utils.init_utils import set_random_seed, setup_saving_and_logging

warnings.filterwarnings("ignore", category=UserWarning)


@hydra.main(version_base=None, config_path="src/configs", config_name="refl_train")
def main(config):
    """
    Main script for training. Instantiates the model, optimizer, scheduler,
    logger, writer, and dataloaders. Runs Trainer to train and
    evaluate the model.

    Args:
        config (DictConfig): hydra experiment config.
    """
    set_random_seed(config.trainer.seed)

    project_config = OmegaConf.to_container(config)
    logger = setup_saving_and_logging(config)
    writer = instantiate(config.writer, logger, project_config)

    if config.trainer.device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    else:
        device = config.trainer.device

    # accelerator = instantiate(config.accelerator)
    # weight_dtype = torch.float16 if accelerator.mixed_precision == "fp16" else torch.float32

    # device = accelerator.device

    model = instantiate(config.model).to(device)
    # build stable diffusion models

    # build reward models
    train_reward_model = instantiate(
        config.reward_models["train_model"], device=device
    ).to(device)
    train_reward_model.requires_grad_(False)

    val_reward_models = []
    for reward_model_config in config.reward_models["val_models"]:
        reward_model = instantiate(reward_model_config, device=device).to(device)
        reward_model.requires_grad_(False)
        val_reward_models.append(reward_model)

    all_models_with_tokenizer = val_reward_models + [model, train_reward_model]

    # setup data_loader instances
    # batch_transforms should be put on device
    dataloaders, batch_transforms = get_dataloaders(
        config,
        device=device,
        all_models_with_tokenizer=all_models_with_tokenizer,
    )

    # build optimizer, learning rate scheduler
    trainable_params = filter(lambda p: p.requires_grad, model.parameters())
    optimizer = instantiate(config.optimizer, params=trainable_params)
    lr_scheduler = instantiate(config.lr_scheduler, optimizer=optimizer)
    scaler = GradScaler()

    # epoch_len = number of iterations for iteration-based training
    # epoch_len = None or len(dataloader) for epoch-based training
    epoch_len = config.trainer.get("epoch_len")

    trainer = ReFLTrainer(
        model=model,
        train_reward_model=train_reward_model,
        val_reward_models=val_reward_models,
        optimizer=optimizer,
        lr_scheduler=lr_scheduler,
        scaler=scaler,
        config=config,
        device=device,
        dataloaders=dataloaders,
        epoch_len=epoch_len,
        logger=logger,
        writer=writer,
        batch_transforms=batch_transforms,
        skip_oom=config.trainer.get("skip_oom", True),
    )

    trainer.train()


if __name__ == "__main__":
    main()
