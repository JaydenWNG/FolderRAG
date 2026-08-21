import {
useCallback,
useEffect,
useState,
} from "react";

import {
BookOpen,
Check,
CircleCheck,
Files,
FolderOpen,
HardDrive,
LibraryBig,
LoaderCircle,
Plus,
RefreshCw,
Search,
Settings2,
} from "lucide-react";

import {
getFolders,
getVectorStatus,
indexFolder,
pickFolder,
registerFolder,
scanFolder,
type Folder as FolderType,
type VectorStatus,
} from "./api";

import DocumentsView from "./DocumentsView";

import "./App.css";


type FolderWithStatus =
FolderType & {
	status?: VectorStatus;
};


type ActiveView =
| "sources"
| "documents";


function App() {
const [
	activeView,
	setActiveView,
] = useState<ActiveView>(
	"sources",
);

const [
	folders,
	setFolders,
] = useState<
	FolderWithStatus[]
>([]);

const [
	loading,
	setLoading,
] = useState(true);

const [
	error,
	setError,
] = useState<
	string | null
>(null);

const [
	addingFolder,
	setAddingFolder,
] = useState(false);

const [
	syncingFolderId,
	setSyncingFolderId,
] = useState<
	number | null
>(null);

const [
	notice,
	setNotice,
] = useState<
	string | null
>(null);


const loadKnowledgeSources =
	useCallback(
	async () => {
		try {
		setError(null);

		const registeredFolders =
			await getFolders();

		const withStatus =
			await Promise.all(
			registeredFolders.map(
				async (
				folder,
				) => {
				try {
					const status =
					await getVectorStatus(
						folder.id,
					);

					return {
					...folder,
					status,
					};

				} catch {
					return folder;
				}
				},
			),
			);

		setFolders(
			withStatus,
		);

		} catch (
		loadError
		) {
		setError(
			loadError
			instanceof Error
			? loadError.message
			: (
				"Something "
				+ "went wrong."
			),
		);

		} finally {
		setLoading(false);
		}
	},
	[],
	);


useEffect(() => {
	void loadKnowledgeSources();
}, [
	loadKnowledgeSources,
]);


async function syncFolder(
	folderId: number,
) {
	setSyncingFolderId(
	folderId,
	);

	setError(null);
	setNotice(null);

	try {
	const scan =
		await scanFolder(
		folderId,
		);

	const index =
		await indexFolder(
		folderId,
		);

	const changed =
		scan.new
		+ scan.changed
		+ scan.deleted;

	if (changed === 0) {
		setNotice(
		"Everything is already "
		+ "up to date.",
		);

	} else {
		const indexedChunks =
		index.indexed_chunks;

		setNotice(
		`Synced ${changed} `
		+ (
			changed === 1
			? "change."
			: "changes."
		)
		+ ` ${indexedChunks} `
		+ (
			indexedChunks === 1
			? "chunk indexed."
			: "chunks indexed."
		),
		);
	}

	await loadKnowledgeSources();

	} catch (
	syncError
	) {
	setError(
		syncError
		instanceof Error
		? syncError.message
		: (
			"Unable to sync "
			+ "folder."
		),
	);

	} finally {
	setSyncingFolderId(
		null,
	);
	}
}


async function addFolder() {
	if (addingFolder) {
	return;
	}

	setAddingFolder(true);

	setError(null);
	setNotice(null);

	try {
	const selection =
		await pickFolder();

	if (
		!selection.selected
		|| !selection.path
	) {
		return;
	}

	const folder =
		await registerFolder(
		selection.path,
		);

	setNotice(
		`Added ${folder.name}. `
		+ "Building its index...",
	);

	await syncFolder(
		folder.id,
	);

	} catch (
	addError
	) {
	setError(
		addError
		instanceof Error
		? addError.message
		: (
			"Unable to add "
			+ "folder."
		),
	);

	} finally {
	setAddingFolder(false);

	await loadKnowledgeSources();
	}
}


const totalDocuments =
	folders.reduce(
	(
		total,
		folder,
	) =>
		total
		+ (
		folder.status
			?.documents
		?? 0
		),
	0,
	);

const totalChunks =
	folders.reduce(
	(
		total,
		folder,
	) =>
		total
		+ (
		folder.status
			?.collection_points
		?? 0
		),
	0,
	);

const totalPending =
	folders.reduce(
	(
		total,
		folder,
	) =>
		total
		+ (
		folder.status
			?.document_statuses
			?.pending
		?? 0
		),
	0,
	);


return (
	<div className="app-shell">
	<aside className="sidebar">
		<div className="brand">
		<div className="brand-mark">
			<BookOpen
			size={21}
			/>
		</div>

		<div className="brand-copy">
			<strong>
			FolderRAG
			</strong>

			<span>
			Local Knowledge
			</span>
		</div>
		</div>


		<div className="sidebar-section-label">
		Workspace
		</div>


		<nav className="navigation">
		<button
			className={
			activeView
			=== "sources"
				? "nav-item active"
				: "nav-item"
			}
			onClick={() => {
			setActiveView(
				"sources",
			);
			}}
		>
			<LibraryBig
			size={18}
			/>

			<span>
			Knowledge Sources
			</span>
		</button>


		<button
			className="nav-item"
		>
			<Search
			size={18}
			/>

			<span>
			Search
			</span>
		</button>


		<button
			className={
			activeView
			=== "documents"
				? "nav-item active"
				: "nav-item"
			}
			onClick={() => {
			setActiveView(
				"documents",
			);
			}}
		>
			<Files
			size={18}
			/>

			<span>
			Documents
			</span>
		</button>
		</nav>


		<div className="sidebar-section-label system-label">
		System
		</div>


		<nav className="navigation">
		<button
			className="nav-item"
		>
			<Settings2
			size={18}
			/>

			<span>
			System Status
			</span>
		</button>
		</nav>


		<div className="sidebar-footer">
		<div className="local-status">
			<span
			className="status-dot"
			/>

			<div>
			<strong>
				Local index
			</strong>

			<span>
				Ready
			</span>
			</div>
		</div>
		</div>
	</aside>


	<main className="main-content">
		{activeView === "documents" ? (
		<DocumentsView
			folders={folders}
		/>
		) : (
		<>
			<header className="page-header">
			<div>
				<p className="eyebrow">
				Your Knowledge
				</p>

				<h1>
				Knowledge Sources
				</h1>

				<p className="subtitle">
				Organize and explore
				the folders available
				to your local
				knowledge engine.
				</p>
			</div>


			<button
				className="primary-button"
				onClick={() => {
				void addFolder();
				}}
				disabled={
				addingFolder
				}
			>
				{addingFolder ? (
				<LoaderCircle
					size={17}
					className="spin"
				/>
				) : (
				<Plus size={17} />
				)}

				{addingFolder
				? "Adding..."
				: "Add folder"}
			</button>
			</header>


			<section className="summary-grid">
			<article className="summary-card">
				<div className="summary-icon">
				<FolderOpen
					size={19}
				/>
				</div>

				<div>
				<span>
					Sources
				</span>

				<strong>
					{folders.length}
				</strong>
				</div>
			</article>


			<article className="summary-card">
				<div className="summary-icon">
				<Files size={19} />
				</div>

				<div>
				<span>
					Tracked files
				</span>

				<strong>
					{totalDocuments}
				</strong>
				</div>
			</article>


			<article className="summary-card">
				<div className="summary-icon">
				<BookOpen
					size={19}
				/>
				</div>

				<div>
				<span>
					Knowledge chunks
				</span>

				<strong>
					{totalChunks}
				</strong>
				</div>
			</article>


			<article className="summary-card">
				<div className="summary-icon">
				<HardDrive
					size={19}
				/>
				</div>

				<div>
				<span>
					Pending
				</span>

				<strong>
					{totalPending}
				</strong>
				</div>
			</article>
			</section>


			<section className="sources-section">
			<div className="section-header">
				<div>
				<h2>
					Indexed folders
				</h2>

				<p>
					Local folders
					currently available
					for retrieval.
				</p>
				</div>

				<span className="source-count">
				{folders.length}
				{" "}
				{folders.length === 1
					? "source"
					: "sources"}
				</span>
			</div>


			{notice && (
				<div className="notice-card">
				<Check size={15} />

				{notice}
				</div>
			)}


			{loading && (
				<div className="message-card">
				Loading your
				knowledge sources...
				</div>
			)}


			{error && (
				<div className="message-card error">
				{error}
				</div>
			)}


			{!loading
				&& !error
				&& folders.length === 0
				&& (
				<div className="empty-state">
					<div className="empty-icon">
					<FolderOpen
						size={25}
					/>
					</div>

					<h3>
					No knowledge
					sources yet
					</h3>

					<p>
					Add a local folder
					to begin building
					your searchable
					knowledge index.
					</p>

					<button
					className="secondary-button"
					onClick={() => {
						void addFolder();
					}}
					disabled={
						addingFolder
					}
					>
					<Plus
						size={16}
					/>

					Add your first
					folder
					</button>
				</div>
				)}


			<div className="folder-list">
				{folders.map(
				(folder) => {
					const indexed =
					folder.status
						?.document_statuses
						?.indexed
					?? 0;

					const pending =
					folder.status
						?.document_statuses
						?.pending
					?? 0;

					const deleted =
					folder.status
						?.document_statuses
						?.deleted
					?? 0;

					const chunks =
					folder.status
						?.collection_points
					?? 0;

					const syncing =
					syncingFolderId
					=== folder.id;

					const ready =
					pending === 0
					&& !syncing;


					return (
					<article
						className="folder-card"
						key={folder.id}
					>
						<div className="folder-card-top">
						<div className="folder-identity">
							<div className="folder-icon">
							<FolderOpen
								size={22}
							/>
							</div>

							<div>
							<div className="folder-title-row">
								<h3>
								{folder.name}
								</h3>

								<span
								className={
									ready
									? "ready-badge"
									: "pending-badge"
								}
								>
								{syncing ? (
									<>
									<LoaderCircle
										size={13}
										className="spin"
									/>

									Syncing
									</>
								) : ready ? (
									<>
									<CircleCheck
										size={13}
									/>

									Ready
									</>
								) : (
									<>
									{pending}
									{" "}
									pending
									</>
								)}
								</span>
							</div>

							<p className="folder-path">
								{folder.path}
							</p>
							</div>
						</div>


						<button
							className="sync-button"
							onClick={() => {
							void syncFolder(
								folder.id,
							);
							}}
							disabled={
							syncingFolderId
							!== null
							}
						>
							{syncing ? (
							<LoaderCircle
								size={15}
								className="spin"
							/>
							) : (
							<RefreshCw
								size={15}
							/>
							)}

							{syncing
							? "Syncing..."
							: "Sync"}
						</button>
						</div>


						<div className="folder-divider" />


						<div className="folder-stats">
						<div className="folder-stat">
							<span>
							Documents
							</span>

							<strong>
							{
								folder.status
								?.documents
								?? 0
							}
							</strong>
						</div>


						<div className="folder-stat">
							<span>
							Indexed
							</span>

							<strong>
							{indexed}
							</strong>
						</div>


						<div className="folder-stat">
							<span>
							Pending
							</span>

							<strong>
							{pending}
							</strong>
						</div>


						<div className="folder-stat">
							<span>
							Deleted
							</span>

							<strong>
							{deleted}
							</strong>
						</div>


						<div className="folder-stat">
							<span>
							Chunks
							</span>

							<strong>
							{chunks}
							</strong>
						</div>
						</div>


						<div className="folder-footer">
						<span>
							Local source
						</span>

						<span>
							Folder #
							{folder.id}
						</span>
						</div>
					</article>
					);
				},
				)}
			</div>
			</section>
		</>
		)}
	</main>
	</div>
);
}


export default App;