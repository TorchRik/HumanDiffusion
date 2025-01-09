import random

import torch

from src.constants.dataset import DatasetColumns
from src.trainer.base_trainer import BaseTrainer


class ReFLTrainer(BaseTrainer):
    """
    Trainer class.
    Reproduce ReFL training.
    """

    def _sample_image_eval(self, batch: dict[str, torch.Tensor]):
        self.model.set_timesteps(self.cfg_trainer.max_mid_timestep, device=self.device)

        mid_timestep = (
            random.randint(
                self.cfg_trainer.min_mid_timestep,
                self.cfg_trainer.max_mid_timestep - 1,
            )
            if self.is_train
            else self.cfg_trainer.max_mid_timestep - 1
        )

        with torch.no_grad():
            latents, encoder_hidden_states = self.model.do_k_diffusion_steps(
                latents=None,
                start_timestamp_index=0,
                end_timestamp_index=mid_timestep,
                input_ids=batch[DatasetColumns.tokenized_text.name],
                return_pred_original=False,
            )

        batch["image"] = self.model.sample_image(
            latents=latents,
            start_timestamp_index=mid_timestep,
            end_timestamp_index=mid_timestep + 1,
            encoder_hidden_states=encoder_hidden_states,
        )

    def _sample_image_train(self, batch: dict[str, torch.Tensor]):
        self._sample_image_eval(batch)
