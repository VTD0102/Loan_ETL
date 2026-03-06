{{ config(materialized='table') }}

SELECT *
FROM {{ source('bronze', 'loans_raw') }}