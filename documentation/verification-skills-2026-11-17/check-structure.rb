# Local structural validation using the existing Ruby YAML parser; installs nothing.
require 'yaml'
require 'json'
require 'digest'
require 'time'
require 'fileutils'

root = File.expand_path('../..', __dir__)
output_dir = File.join(root, 'build', 'verification', 'skills')
FileUtils.mkdir_p(output_dir)
report_path = File.join(output_dir, 'structure.json')
previous = File.exist?(report_path) ? JSON.parse(File.read(report_path)) : nil
results = Dir.glob(root + '/.agents/skills/*/SKILL.md').sort.map do |file|
  content = File.read(file)
  match = content.match(/\A---\n(.*?)\n---\n/m)
  raise "Frontmatter absent: #{file}" unless match
  meta = YAML.safe_load(match[1])
  name = File.basename(File.dirname(file))
  raise 'Name mismatch' unless meta['name'] == name && name.match?(/\A[a-z0-9]+(?:-[a-z0-9]+)*\z/) && name.length < 64
  raise 'Invalid description' unless meta['description'].is_a?(String) && (1..1024).include?(meta['description'].length)
  raise 'Unexpected fields' unless (meta.keys - ['name', 'description', 'metadata']).empty?
  raise 'Unfinished placeholder' if content.include?('[TODO:')
  links = content.scan(/\[[^\]]+\]\(([^)]+)\)/).flatten
  links.reject! { |link| link.start_with?('https://', 'http://') }
  checked = links.map do |link|
    resolved = File.expand_path(link.split('#')[0], File.dirname(file))
    raise "Missing reference: #{resolved}" unless File.file?(resolved) || File.directory?(resolved)
    {link: link, resolved: resolved, exists: true}
  end
  {name: name, file: file, status: 'PASS', sha256: Digest::SHA256.hexdigest(content), references: checked}
end
raise 'Expected nine skills' unless results.size == 9
report = {observed_at: Time.now.utc.iso8601, command: 'ruby documentation/verification-skills-2026-11-17/check-structure.rb',
          parser: 'Ruby YAML.safe_load (Psych)',
          scope: 'Frontmatter YAML, naming, required fields, placeholders, local links; not behavior or discovery',
          official_validator: {status: 'BLOCKED_DEPENDENCY', reason: 'python3 quick_validate.py: ModuleNotFoundError yaml; no dependency installed'},
          results: results}
if previous
  report[:previous_checks] = previous.fetch('previous_checks', []) +
    [{observed_at: previous['observed_at'], revisions: previous['results'].map { |x| {name: x['name'], sha256: x['sha256']} }}]
end
File.write(report_path, JSON.pretty_generate(report) + "\n")
puts JSON.generate({status: 'PASS', skills: results.size, local_references: results.sum { |x| x[:references].size }})
