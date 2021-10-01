import yaml
from dask_predictions.load_bulk_structures import load_ocdata_bulks
from dask_predictions.filters import bulk_filter, adsorbate_filter
from dask_predictions.load_adsorbate_structures import load_ocdata_adsorbates
from dask_predictions.enumerate_slabs_adslabs import enumerate_slabs, enumerate_adslabs
import dask.bag as db
import dask
import sys
from joblib import Memory

# Load inputs and define global vars
if __name__ == "__main__":

    # Load the config yaml
    config_path = sys.argv[1]
    with open(config_path) as f:
        config = yaml.safe_load(f)

    # set up the dask cluster using the config block
    exec(config["dask_config"])

    # Set up joblib memory to use for caching hard steps
    memory = Memory(config["memory_cache_location"], verbose=1)

    # Load and filter the bulks
    bulks_delayed = dask.delayed(load_ocdata_bulks)()
    bulk_bag = db.from_delayed([bulks_delayed])
    bulk_df = bulk_bag.to_dataframe()
    filtered_catalyst_df = bulk_filter(config, bulk_df)
    print(
        "Total number of filtered bulks is %d" % filtered_catalyst_df.compute().shape[0]
    )

    # Load and filter the adsorbates
    adsorbate_delayed = dask.delayed(load_ocdata_adsorbates)()
    adsorbate_bag = db.from_delayed([adsorbate_delayed])
    adsorbate_df = adsorbate_bag.to_dataframe()
    filtered_adsorbate_df = adsorbate_filter(config, adsorbate_df)
    filtered_adsorbate_df = filtered_adsorbate_df.persist()
    print(
        "Total number of filtered adsorbates is %d"
        % filtered_adsorbate_df.shape[0].compute()
    )

    # Enumerate surfaces
    filtered_catalyst_df["surfaces"] = filtered_catalyst_df.bulk_atoms.apply(
        memory.cache(enumerate_slabs), meta=("surfaces", "object")
    )
    filtered_catalyst_df = filtered_catalyst_df.explode("surfaces")
    filtered_catalyst_df = filtered_catalyst_df.persist()

    # Enumerate surface_adsorbate combinations
    df = filtered_catalyst_df.assign(key=1).merge(
        filtered_adsorbate_df.assign(key=1), how="outer", on="key"
    )
    df["adslabs"] = df.apply(
        memory.cache(enumerate_adslabs), meta=("adslabs", "object"), axis=1
    )
    dfout = df.persist()
