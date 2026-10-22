"""Build the MentalScape warehouse.

fetch  downloads collected files from the data-mhsds-monthly release
load   puts the preferred version of each file into the raw schema
The dbt project in warehouse/ then builds the staging and mart layers.
"""
