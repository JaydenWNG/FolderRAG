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