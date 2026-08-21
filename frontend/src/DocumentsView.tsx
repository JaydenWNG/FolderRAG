import {
useEffect,
useMemo,
useState,
} from "react";

import {
AlignLeft,
File,
FileCode2,
FileText,
Layers3,
LoaderCircle,
Search,
} from "lucide-react";

import {
getDocumentChunks,
getDocuments,
getExtractedDocument,
type ChunkPreview,
type DocumentRecord,
type ExtractedDocument,
type Folder,
} from "./api";


type DocumentsViewProps = {
folders: Folder[];
};


type InspectorTab =
| "content"
| "chunks";


function formatBytes(
value: number,
): string {
if (value < 1024) {
	return `${value} B`;
}

if (value < 1024 * 1024) {
	return (
	`${(
		value / 1024
	).toFixed(1)} KB`
	);
}

return (
	`${(
	value
	/ 1024
	/ 1024
	).toFixed(1)} MB`
);
}


function getFileIcon(
extension: string,
) {
if (
	extension === ".py"
) {
	return (
	<FileCode2 size={18} />
	);
}

if (
	extension === ".md"
	|| extension === ".txt"
) {
	return (
	<FileText size={18} />
	);
}

return <File size={18} />;
}


function provenanceText(
item: {
	start_page:
	number | null;

	end_page:
	number | null;

	start_line:
	number | null;

	end_line:
	number | null;
},
): string | null {
if (
	item.start_page !== null
) {
	if (
	item.end_page !== null
	&& item.end_page
	!== item.start_page
	) {
	return (
		`Pages ${item.start_page}`
		+ `–${item.end_page}`
	);
	}

	return (
	`Page ${item.start_page}`
	);
}

if (
	item.start_line !== null
) {
	if (
	item.end_line !== null
	&& item.end_line
	!== item.start_line
	) {
	return (
		`Lines ${item.start_line}`
		+ `–${item.end_line}`
	);
	}

	return (
	`Line ${item.start_line}`
	);
}

return null;
}


export default function DocumentsView({
folders,
}: DocumentsViewProps) {
const [
	selectedFolderId,
	setSelectedFolderId,
] = useState<number | null>(
	folders[0]?.id ?? null,
);

const [
	documents,
	setDocuments,
] = useState<DocumentRecord[]>(
	[],
);

const [
	loadingDocuments,
	setLoadingDocuments,
] = useState(false);

const [
	selectedDocument,
	setSelectedDocument,
] = useState<
	DocumentRecord | null
>(null);

const [
	query,
	setQuery,
] = useState("");

const [
	statusFilter,
	setStatusFilter,
] = useState("all");

const [
	inspectorTab,
	setInspectorTab,
] = useState<InspectorTab>(
	"content",
);

const [
	extracted,
	setExtracted,
] = useState<
	ExtractedDocument | null
>(null);

const [
	chunks,
	setChunks,
] = useState<
	ChunkPreview | null
>(null);

const [
	inspectorLoading,
	setInspectorLoading,
] = useState(false);

const [
	error,
	setError,
] = useState<
	string | null
>(null);


useEffect(() => {
	if (
	selectedFolderId
	!== null
	) {
	return;
	}

	if (folders.length > 0) {
	setSelectedFolderId(
		folders[0].id,
	);
	}
}, [
	folders,
	selectedFolderId,
]);


useEffect(() => {
	async function load() {
	if (
		selectedFolderId
		=== null
	) {
		setDocuments([]);
		return;
	}

	setLoadingDocuments(true);
	setError(null);

	try {
		const result =
		await getDocuments(
			selectedFolderId,
		);

		setDocuments(
		result.documents,
		);

		setSelectedDocument(
		null,
		);

		setExtracted(null);
		setChunks(null);

	} catch (loadError) {
		setError(
		loadError instanceof Error
			? loadError.message
			: (
			"Unable to load "
			+ "documents."
			),
		);

	} finally {
		setLoadingDocuments(
		false,
		);
	}
	}

	void load();
}, [
	selectedFolderId,
]);


async function loadContent(
	document: DocumentRecord,
) {
	if (!document.available) {
	return;
	}

	setInspectorLoading(true);
	setError(null);

	try {
	const result =
		await getExtractedDocument(
		document.id,
		);

	setExtracted(result);

	} catch (loadError) {
	setError(
		loadError instanceof Error
		? loadError.message
		: (
			"Unable to load "
			+ "document content."
		),
	);

	} finally {
	setInspectorLoading(false);
	}
}


async function selectDocument(
	document: DocumentRecord,
) {
	setSelectedDocument(
	document,
	);

	setInspectorTab(
	"content",
	);

	setExtracted(null);
	setChunks(null);

	await loadContent(
	document,
	);
}


async function showChunks() {
	if (
	!selectedDocument
	|| !selectedDocument.available
	) {
	return;
	}

	setInspectorTab(
	"chunks",
	);

	if (chunks) {
	return;
	}

	setInspectorLoading(true);
	setError(null);

	try {
	const result =
		await getDocumentChunks(
		selectedDocument.id,
		);

	setChunks(result);

	} catch (loadError) {
	setError(
		loadError instanceof Error
		? loadError.message
		: (
			"Unable to load "
			+ "document chunks."
		),
	);

	} finally {
	setInspectorLoading(false);
	}
}


const filteredDocuments =
	useMemo(() => {
	const normalizedQuery =
		query
		.trim()
		.toLowerCase();

	return documents.filter(
		(document) => {
		const matchesQuery =
			!normalizedQuery
			|| document
			.relative_path
			.toLowerCase()
			.includes(
				normalizedQuery,
			);

		const matchesStatus =
			statusFilter === "all"
			|| document.status
			=== statusFilter;

		return (
			matchesQuery
			&& matchesStatus
		);
		},
	);
	}, [
	documents,
	query,
	statusFilter,
	]);


return (
	<>
	<header className="page-header">
		<div>
		<p className="eyebrow">
			Knowledge Library
		</p>

		<h1>
			Documents
		</h1>

		<p className="subtitle">
			Browse indexed files and
			inspect how FolderRAG
			extracts and chunks them.
		</p>
		</div>
	</header>


	<section className="documents-toolbar">
		<label className="source-select">
		<span>
			Knowledge source
		</span>

		<select
			value={
			selectedFolderId
			?? ""
			}
			onChange={(event) => {
			setSelectedFolderId(
				Number(
				event.target.value,
				),
			);
			}}
		>
			{folders.map(
			(folder) => (
				<option
				key={folder.id}
				value={folder.id}
				>
				{folder.name}
				</option>
			),
			)}
		</select>
		</label>

		<label className="document-search">
		<Search size={16} />

		<input
			type="search"
			placeholder="Search files..."
			value={query}
			onChange={(event) => {
			setQuery(
				event.target.value,
			);
			}}
		/>
		</label>
	</section>


	<div className="document-filters">
		{[
		"all",
		"indexed",
		"pending",
		"deleted",
		].map((status) => (
		<button
			key={status}
			className={
			statusFilter
			=== status
				? (
				"filter-button "
				+ "active"
				)
				: "filter-button"
			}
			onClick={() => {
			setStatusFilter(
				status,
			);
			}}
		>
			{status[0]
			.toUpperCase()
			+ status.slice(1)}
		</button>
		))}
	</div>


	{error && (
		<div className="message-card error">
		{error}
		</div>
	)}


	<section className="documents-layout">
		<div className="document-browser">
		<div className="document-browser-header">
			<div>
			<strong>
				Files
			</strong>

			<span>
				{
				filteredDocuments
					.length
				}
				{" "}
				shown
			</span>
			</div>
		</div>


		{loadingDocuments ? (
			<div className="document-loading">
			<LoaderCircle
				size={18}
				className="spin"
			/>

			Loading documents...
			</div>

		) : filteredDocuments
			.length === 0 ? (
			<div className="document-loading">
			No matching documents.
			</div>

		) : (
			<div className="document-list">
			{filteredDocuments.map(
				(document) => (
				<button
					key={document.id}
					className={
					selectedDocument
						?.id
					=== document.id
						? (
						"document-row "
						+ "active"
						)
						: "document-row"
					}
					onClick={() => {
					void selectDocument(
						document,
					);
					}}
				>
					<div className="document-type-icon">
					{getFileIcon(
						document.extension,
					)}
					</div>

					<div className="document-row-main">
					<strong>
						{
						document
							.relative_path
						}
					</strong>

					<span>
						{
						document.extension
							.replace(
							".",
							"",
							)
							.toUpperCase()
						}
						{" · "}
						{
						formatBytes(
							document
							.size_bytes,
						)
						}
					</span>
					</div>

					<span
					className={
						`document-status `
						+ document.status
					}
					>
					{document.status}
					</span>
				</button>
				),
			)}
			</div>
		)}
		</div>


		<div className="document-inspector">
		{!selectedDocument ? (
			<div className="inspector-empty">
			<FileText size={28} />

			<h3>
				Select a document
			</h3>

			<p>
				Choose a file to inspect
				its extracted content
				and semantic chunks.
			</p>
			</div>

		) : (
			<>
			<div className="inspector-header">
				<div>
				<span className="inspector-kicker">
					Document inspector
				</span>

				<h2>
					{
					selectedDocument
						.relative_path
					}
				</h2>

				<p>
					{
					formatBytes(
						selectedDocument
						.size_bytes,
					)
					}
					{" · "}
					{
					selectedDocument
						.status
					}
				</p>
				</div>
			</div>


			{!selectedDocument
				.available ? (
				<div className="inspector-empty compact">
				<File size={24} />

				<h3>
					File unavailable
				</h3>

				<p>
					This document is
					retained in the
					index history but
					the local file has
					been deleted.
				</p>
				</div>

			) : (
				<>
				<div className="inspector-tabs">
					<button
					className={
						inspectorTab
						=== "content"
						? "active"
						: ""
					}
					onClick={() => {
						setInspectorTab(
						"content",
						);
					}}
					>
					<AlignLeft
						size={15}
					/>
					Extracted content
					</button>

					<button
					className={
						inspectorTab
						=== "chunks"
						? "active"
						: ""
					}
					onClick={() => {
						void showChunks();
					}}
					>
					<Layers3
						size={15}
					/>
					Chunks
					</button>
				</div>


				<div className="inspector-body">
					{inspectorLoading ? (
					<div className="document-loading">
						<LoaderCircle
						size={18}
						className="spin"
						/>
						Loading...
					</div>

					) : inspectorTab
					=== "content" ? (
					<div className="content-list">
						{extracted
						?.sections
						.map(
							(
							section,
							index,
							) => (
							<article
								className="content-block"
								key={index}
							>
								<div className="content-meta">
								<span>
									{
									section
										.heading
									?? section
										.symbol
									?? section
										.section_type
									}
								</span>

								{provenanceText(
									section,
								) && (
									<span>
									{
										provenanceText(
										section,
										)
									}
									</span>
								)}
								</div>

								<pre>
								{
									section.text
								}
								</pre>
							</article>
							),
						)}
					</div>

					) : (
					<div className="content-list">
						<div className="chunk-summary">
						<span>
							{
							chunks
								?.chunk_count
							?? 0
							}
							{" "}
							semantic chunks
						</span>

						{chunks && (
							<span>
							{
								chunks
								.chunker
								.boundary_model
							}
							{" · "}
							{
								chunks
								.chunker
								.device
							}
							</span>
						)}
						</div>

						{chunks
						?.chunks
						.map(
							(chunk) => (
							<article
								className="content-block"
								key={
								chunk
									.chunk_index
								}
							>
								<div className="content-meta">
								<span>
									Chunk{" "}
									{
									chunk
										.chunk_index
									}
									{" · "}
									{
									chunk
										.token_count
									}
									{" tokens"}
								</span>

								{provenanceText(
									chunk,
								) && (
									<span>
									{
										provenanceText(
										chunk,
										)
									}
									</span>
								)}
								</div>

								<pre>
								{
									chunk.text
								}
								</pre>
							</article>
							),
						)}
					</div>
					)}
				</div>
				</>
			)}
			</>
		)}
		</div>
	</section>
	</>
);
}