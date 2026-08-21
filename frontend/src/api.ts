export type Folder = {
id: number;
name: string;
path: string;
created_at: string;
};

export type VectorStatus = {
folder_id: number;
documents: number;

document_statuses:
	Record<string, number>;

collection: string;
collection_points: number;

embedding: {
	model: string;
	dimensions: number;
	distance: string;
};
};

export type FolderPickerResult = {
selected: boolean;
path: string | null;
};

export type ScanResult = {
status: string;
folder_id: number;
discovered: number;
new: number;
changed: number;
unchanged: number;
deleted: number;
};

export type IndexResult = {
status: string;
folder_id: number;
pending_documents: number;
indexed_documents: number;
indexed_chunks: number;

deleted_documents_cleaned:
	number;

failed_documents: {
	document_id: number;
	path: string;
	stage: string;
	error: string;
}[];

collection_points: number;
};

export type DocumentRecord = {
id: number;
relative_path: string;
extension: string;
size_bytes: number;
sha256: string;
status: string;
updated_at: string;
available: boolean;
};

export type DocumentList = {
folder_id: number;
folder_name: string;
folder_path: string;

documents: DocumentRecord[];
};

export type ExtractedSection = {
text: string;

start_line:
	number | null;

end_line:
	number | null;

start_page:
	number | null;

end_page:
	number | null;

heading:
	string | null;

symbol:
	string | null;

section_type: string;
};

export type ExtractedDocument = {
document_id: number;
path: string;
extension: string;
sections: ExtractedSection[];
};

export type DocumentChunk = {
chunk_index: number;
section_index: number;
text: string;
token_count: number;
strategy: string;

start_line:
	number | null;

end_line:
	number | null;

start_page:
	number | null;

end_page:
	number | null;

heading:
	string | null;

symbol:
	string | null;

section_type: string;
};

export type ChunkPreview = {
document_id: number;
path: string;
chunk_count: number;

chunker: {
	strategy: string;
	boundary_model: string;
	device: string;
};

chunks: DocumentChunk[];
};


async function getErrorMessage(
response: Response,
): Promise<string> {
try {
	const body = await response.json();

	if (
	typeof body.detail
	=== "string"
	) {
	return body.detail;
	}
} catch {
	// Fall through.
}

return (
	`Request failed with `
	+ `${response.status}.`
);
}


export async function getFolders():
Promise<Folder[]> {
const response = await fetch(
	"/api/folders",
);

if (!response.ok) {
	throw new Error(
	await getErrorMessage(
		response,
	),
	);
}

return response.json();
}


export async function pickFolder():
Promise<FolderPickerResult> {
const response = await fetch(
	"/api/folders/pick",
	{
	method: "POST",
	},
);

if (!response.ok) {
	throw new Error(
	await getErrorMessage(
		response,
	),
	);
}

return response.json();
}


export async function registerFolder(
path: string,
): Promise<Folder> {
const response = await fetch(
	"/api/folders",
	{
	method: "POST",

	headers: {
		"Content-Type":
		"application/json",
	},

	body: JSON.stringify({
		path,
	}),
	},
);

if (!response.ok) {
	throw new Error(
	await getErrorMessage(
		response,
	),
	);
}

return response.json();
}


export async function getVectorStatus(
folderId: number,
): Promise<VectorStatus> {
const response = await fetch(
	`/api/index/vectors/${folderId}`,
);

if (!response.ok) {
	throw new Error(
	await getErrorMessage(
		response,
	),
	);
}

return response.json();
}


export async function scanFolder(
folderId: number,
): Promise<ScanResult> {
const response = await fetch(
	`/api/index/scan/${folderId}`,
	{
	method: "POST",
	},
);

if (!response.ok) {
	throw new Error(
	await getErrorMessage(
		response,
	),
	);
}

return response.json();
}


export async function indexFolder(
folderId: number,
): Promise<IndexResult> {
const response = await fetch(
	`/api/index/vectors/${folderId}`,
	{
	method: "POST",
	},
);

if (!response.ok) {
	throw new Error(
	await getErrorMessage(
		response,
	),
	);
}

return response.json();
}


export async function getDocuments(
folderId: number,
): Promise<DocumentList> {
const response = await fetch(
	`/api/documents/folder/${folderId}`,
);

if (!response.ok) {
	throw new Error(
	await getErrorMessage(
		response,
	),
	);
}

return response.json();
}


export async function getExtractedDocument(
documentId: number,
): Promise<ExtractedDocument> {
const response = await fetch(
	`/api/index/extract/${documentId}`,
);

if (!response.ok) {
	throw new Error(
	await getErrorMessage(
		response,
	),
	);
}

return response.json();
}


export async function getDocumentChunks(
documentId: number,
): Promise<ChunkPreview> {
const response = await fetch(
	`/api/index/chunks/${documentId}`,
);

if (!response.ok) {
	throw new Error(
	await getErrorMessage(
		response,
	),
	);
}

return response.json();
}