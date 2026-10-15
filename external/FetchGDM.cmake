# FetchGDM(<source-dir> <tag>)
#
# Keeps a copy of the gdm sources at <source-dir>, tracking the
# head commit of <tag> (a branch name, a tag, or a commit hash). No git and
# no GitHub API calls are involved; on every configure it runs this pipeline:
#
#   recover    finish or clean up a swap left over from a crashed run
#
#   resolve    fetch latest commit of <tag> from GitHub's commit Atom feed
#
#   compare    check if the installed copy is the latest via GDM_COMMIT
#
#   download   if local is outdated, download latest archive
#
#   verify     check gzip magic number and extract into a per-target scratch dir
#
#   install    extracted dir is staged next to <source-dir> (same filesystem)
#              and swapped in.
#              Previous copy is renamed as <source-dir>.old and restored on failure
#
# The scratch files follow gdm's own conventions (Dependencies.cmake shares
# ${CMAKE_BINARY_DIR}/_gdm_downloads and _gdm_extract, keyed <name>-<tag>),
# so the two mechanisms never sweep each other's files.
#
# Every failure before the install degrades to "keep using the existing
# checkout" (WARNING). FATAL_ERROR is reserved for cases with nothing usable
# to build against, or an install that could not be completed cleanly.
function(FetchGDM source_dir tag)

	### recover: finish or clean up a swap left over from a crashed run

	if(EXISTS "${source_dir}.old") # leftovers of a crashed previous run
		if(EXISTS "${source_dir}")
			# previous install finished; the backup is obsolete
			file(REMOVE_RECURSE "${source_dir}.old")
		else()
			# target missing: finish the interrupted swap
			file(RENAME "${source_dir}.old" "${source_dir}")
		endif()
	endif()

	### resolve: <tag> -> head commit

	set(ref "")
	message(STATUS "GDM: checking upstream '${tag}'")
	# per-tag cache file in gdm's download dir, keyed like its archives
	string(REGEX REPLACE "[^A-Za-z0-9._-]" "_" tag_safe "${tag}")
	set(feed_file "${CMAKE_BINARY_DIR}/_gdm_downloads/gdm-${tag_safe}.atom")
	file(MAKE_DIRECTORY "${CMAKE_BINARY_DIR}/_gdm_downloads")
	file(DOWNLOAD
		"https://github.com/awidesky/gdm/commits/${tag}.atom"
		"${feed_file}"
		TIMEOUT 10 # a dead connection must not hang the configure
		TLS_VERIFY ON
		STATUS dl
	)
	list(GET dl 0 code)
	set(fetch_err "")
	if(code EQUAL 0)
		# feed downloaded: scrape the head commit out of it. A failed match
		# (feed format changed) leaves ref empty, which the compare stage
		# treats exactly like a network failure.
		file(READ "${feed_file}" feed)
		string(REGEX MATCH "gdm/commit/([0-9a-f]+)" m "${feed}")
		set(ref "${CMAKE_MATCH_1}")
		if(ref STREQUAL "")
			set(fetch_err "could not parse the commit Atom feed")
		endif()
	else()
		list(GET dl 1 fetch_err)
		string(REGEX REPLACE "^\"|\"$" "" fetch_err "${fetch_err}") # STATUS quotes the message
	endif()
	string(SUBSTRING "${ref}" 0 7 ref_short) # short hash, for messages only

	### compare: decide whether anything must happen

	set(need_fetch TRUE)
	if(ref STREQUAL "") # offline / timeout / feed format changed
		if(EXISTS "${source_dir}/CMakeLists.txt")
			set(need_fetch FALSE) # degrade: keep building against the old copy
			message(WARNING "GDM: cannot fetch '${tag}' (${fetch_err}); using existing checkout")
		else()
			# nothing to build against, and no way to get it
			message(FATAL_ERROR "GDM: cannot fetch '${tag}' (${fetch_err}), and no gdm sources in ${source_dir}")
		endif()
	elseif(EXISTS "${source_dir}/GDM_COMMIT" AND EXISTS "${source_dir}/CMakeLists.txt")
		file(READ "${source_dir}/GDM_COMMIT" have)
		string(STRIP "${have}" have)
		if(have STREQUAL ref)
			set(need_fetch FALSE) # marker matches the upstream head: nothing to do
			message(STATUS "GDM is up to date(${ref_short})")
		else()
			string(SUBSTRING "${have}" 0 7 have_short)
			message(STATUS "GDM: update ${have_short} -> ${ref_short}")
		endif()
	endif()

	### download: if need_fetch, download the archive tarball

	set(archive "")
	set(fetch_err "") # reset: verify's discard messages carry their own reasons
	if(need_fetch)
		set(url "https://github.com/awidesky/gdm/archive/${ref}.tar.gz")
		# downloaded archive stays, overwritten on the next fetch.
		set(archive "${CMAKE_BINARY_DIR}/_gdm_downloads/gdm.tar.gz")
		message(STATUS "GDM: downloading ${url}")
		file(DOWNLOAD "${url}" "${archive}" TLS_VERIFY ON TIMEOUT 300 INACTIVITY_TIMEOUT 30 STATUS dl)
		list(GET dl 0 code)
		if(NOT code EQUAL 0)
			list(GET dl 1 fetch_err)
			string(REGEX REPLACE "^\"|\"$" "" fetch_err "${fetch_err}") # STATUS quotes the message
			# download failed; DOWNLOAD leaves an empty file behind
			file(REMOVE "${archive}")
			unset(archive)
		endif()
	endif()

	### verify: extract into a per-target scratch dir and prove the content

	set(root "")
	if(archive)
		file(READ "${archive}" magic LIMIT 2 HEX)
		if(NOT magic STREQUAL "1f8b") # gzip magic: rejects 404 pages / empty files
			message(WARNING "GDM: ${url} did not return a tarball; discarding it")
			file(REMOVE "${archive}")
			unset(archive)
		else()
			# gdm's Dependencies.cmake extracts each package into its own
			# _gdm_extract/<name>-<tag> dir; do the same
			set(extract_dir "${CMAKE_BINARY_DIR}/_gdm_extract/gdm-${ref}")
			file(REMOVE_RECURSE "${extract_dir}")
			file(ARCHIVE_EXTRACT INPUT "${archive}" DESTINATION "${extract_dir}")
			file(GLOB root LIST_DIRECTORIES true "${extract_dir}/*")
			get_filename_component(name "${root}" NAME)
			# GitHub names the archive root gdm-<commit>
			# also reject empty or multi-root extractions
			if(NOT name STREQUAL "gdm-${ref}" OR NOT EXISTS "${root}/CMakeLists.txt")
				message(WARNING "GDM: unexpected archive content from ${url}; discarding it")
				file(REMOVE_RECURSE "${extract_dir}")
				file(REMOVE "${archive}")
				unset(archive)
				set(root "")
			endif()
		endif()
	endif()

	### install: swap the verified copy in, fall back on any failure

	if(archive)
		# the GDM_COMMIT is written into the staged copy
		file(WRITE "${root}/GDM_COMMIT" "${ref}\n")
		set(stage "${source_dir}.new")
		# stage next to the target: file(COPY) works across filesystems, and
		# the final renames below are then atomic within one directory
		file(REMOVE_RECURSE "${stage}")
		file(COPY "${root}/" DESTINATION "${stage}")
		unset(swap)
		if(EXISTS "${source_dir}") # park the old copy (atomic, non-destructive)
			file(RENAME "${source_dir}" "${source_dir}.old" RESULT swap)
		endif()
		if(NOT swap) # park ok (or nothing to park): install the new copy
			file(RENAME "${stage}" "${source_dir}" RESULT swap)
		endif()
		if(swap) # install failed: undo the park so nothing is lost
			if(EXISTS "${source_dir}.old")
				file(RENAME "${source_dir}.old" "${source_dir}" RESULT back)
				if(back) # even the restore failed; point the user at the backup
					message(FATAL_ERROR "GDM: install failed (${swap}); previous sources left in ${source_dir}.old")
				endif()
				message(FATAL_ERROR "GDM: install failed (${swap}); previous sources restored")
			elseif(EXISTS "${source_dir}") # park failed; the old copy never moved
				message(FATAL_ERROR "GDM: install failed: ${swap}; existing sources unchanged")
			else() # first install; nothing existed to lose
				message(FATAL_ERROR "GDM: install failed: ${swap}")
			endif()
		endif()
		# success: the backup and this target's scratch dir are no longer needed
		file(REMOVE_RECURSE "${source_dir}.old" "${extract_dir}")
	elseif(need_fetch) # no usable archive: degrade to the old copy, or abort
		set(err_note "")
		if(fetch_err)
			set(err_note " (${fetch_err})")
		endif()
		if(EXISTS "${source_dir}/CMakeLists.txt")
			message(WARNING "GDM: could not fetch ${ref_short}${err_note}; using existing checkout")
		else()
			message(FATAL_ERROR "GDM: could not fetch gdm${err_note}, and no gdm sources in ${source_dir}")
		endif()
	endif()

endfunction()
