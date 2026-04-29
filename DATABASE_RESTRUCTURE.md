# Database Restructure Summary

## New Structure

### parent_configuration table
- id (PRIMARY KEY)
- parent_file
- source_path
- source_type
- podcast_theme
- podcast_subtheme
- split_configuration
- generation_mode
- combination_state

### podcast_download table
- id (PRIMARY KEY)
- parent_configuration_id (FOREIGN KEY)
- source_id
- podcast_name
- generation_state
- download_state
- conversion_state
- date

## Updated Scripts

1. **setup_database.py** - Creates both tables with proper structure
2. **migrate_restructure_tables.py** - Migration script to restructure existing database
3. **CollectAndSave.py** - Inserts into both tables
4. **delete_all_records.py** - Deletes from both tables
5. **nllm-aws-asl-add-generate-gnl_v2.py** - Uses JOIN to query
6. **nllm-aws-asl-add-generate-gnl_v2_playwright.py** - Uses JOIN to query
7. **nllm-aws-asl-download-rename-gnl_v2.py** - Uses JOIN to query
8. **batch_convert_to_mp3_v2.py** - Uses JOIN to query
9. **combine_mp3_v2.py** - Uses JOIN to query, updates parent_configuration.combination_state
10. **get_title_v2.py** - Uses JOIN to query
11. **process_all_records_for_generation.py** - Uses JOIN to query
12. **process_all_records_for_download.py** - Uses JOIN to query
13. **process_all_records_for_conversion.py** - Uses JOIN to query

## Key Changes

- Parent-level metadata (theme, source_type, split_configuration, etc.) stored in parent_configuration
- Individual file processing states stored in podcast_download
- All queries now use JOIN between the two tables
- combination_state moved to parent_configuration (it's a parent-level state)
- No duplicate columns between tables
