"""Dataset definitions and their committed manifests."""

from . import lrcc_dvnl

DATASETS = {lrcc_dvnl.DATASET_ID: lrcc_dvnl}

__all__ = ["DATASETS", "lrcc_dvnl"]
