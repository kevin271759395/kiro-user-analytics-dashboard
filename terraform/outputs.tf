output "aws_region" {
  description = "AWS region"
  value       = var.aws_region
}

output "glue_database_name" {
  description = "Name of the Glue database"
  value       = aws_glue_catalog_database.analytics_db.name
}

output "glue_crawler_name" {
  description = "Name of the Glue crawler"
  value       = aws_glue_crawler.analytics_crawler.name
}

output "athena_output_location" {
  description = "S3 location for Athena query results"
  value       = "s3://${aws_s3_bucket.athena_results.bucket}/"
}

output "identity_store_id" {
  description = "IAM Identity Center Identity Store ID"
  value       = var.identity_store_id
}

output "s3_data_path" {
  description = "Full S3 data path including account ID and region"
  value       = "s3://${local.s3_data_path}/"
}

output "prompt_log_s3_uri" {
  description = "S3 URI for Kiro prompt logs"
  value       = var.prompt_log_s3_uri
}
