export function isDeveloperInfoEnabled(
  value = process.env.NEXT_PUBLIC_ENABLE_DEVELOPER_INFO,
) {
  return value === "true";
}
