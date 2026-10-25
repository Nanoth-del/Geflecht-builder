# GeflechtEQ isolated unsigned IPA builder

This public controller builds one private iOS project on an ephemeral macOS
runner. The private source tree, Xcode output, package-resolution details,
archive, IPA, checksums, and audit logs never leave the runner except for the
verified unsigned IPA published to the project's private prerelease.

## Public metadata boundary

This repository intentionally exposes only the controller, its target project
identity, and an immutable source commit SHA supplied at dispatch. It does not
publish source files, private credentials, build paths, compiler diagnostics,
checksums, or an IPA artifact. The workflow accepts no repository, project,
scheme, application-name, or Release-destination input.

The IPA necessarily retains runtime bundle metadata required by iOS, such as
the bundle identifier, app name, and version. It is not a signed or installable
distribution artifact; re-sign it privately before installation.

## Required existing credential

The current public controller uses the pre-existing repository secret
`GEFLECHTEQ`. The workflow is fixed to one source and one private Release
destination, so the secret cannot be redirected through dispatch inputs.
Never paste its value into source, workflow inputs, release notes, issues, or
Actions logs.

This shared read/write credential is an explicitly accepted operational
boundary for the current release. A future hardening pass can split it into
separate source-read and Release-write environment secrets once those values
are available for migration.

## Dispatch contract

Run **GeflechtEQ private unsigned IPA build** with the exact, lowercase,
40-character source commit SHA. The workflow rejects branches, tags, short
SHAs, and arbitrary source / Release destinations.

The workflow performs all of the following privately:

1. Fetches and verifies the requested immutable source revision using the
   source-read credential without persisting it in Git configuration.
2. Resolves packages, cleans, and archives with signing disabled.
3. Packages the IPA and audits it for source/build products, profiles,
   signatures, source paths, runner paths, credential patterns, and unwanted
   archive metadata.
4. Publishes only to the private prerelease, downloads that asset back using
   the release-write credential, and verifies its SHA-256 digest before
   cleanup.
5. Removes the private checkout, archive, derived data, IPA copies, audit
   directory, verification copy, and every captured log with `if: always()`.

## WAR protected profile

**WAR protected unsigned iOS build** is a separate manual-only controller in
`protected-war-ios.yml`. It uses the existing `WAR` repository secret and one
fixed private repository identity. It accepts no dispatch inputs and resolves
private `main` to an immutable revision without exposing that revision in this
public repository. The app's source version and build number remain unchanged.

Build output and diagnostics stay in runner-local files. Successful builds
upload the five contracted deliverables to a draft private prerelease, download
and compare every asset and its checksum manifest, then publish and repeat the
verification. Failure diagnostics may be retained only in a draft release in
the same private repository. No public artifact or cache is created. Temporary
source, build products, verification copies, and logs are erased on every run.
