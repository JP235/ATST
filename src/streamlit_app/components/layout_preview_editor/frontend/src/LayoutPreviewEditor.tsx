import React, { useCallback, useEffect, useRef, useState } from 'react';
import ReactDOM from 'react-dom/client';
import './LayoutPreviewEditor.css';

export type LayoutRow = Record<string, string>;

export interface LayoutPreviewEditorProps {
    layoutData?: LayoutRow[];
    columns?: string[];
    plateFormat?: string;
    plateFormats?: string[];
    initialMode?: Mode;
    showFullDataTable?: boolean;
}

type ComponentAction = 'sync' | 'lock' | 'apply' | 'cancel';

interface ComponentValue {
    mode: Mode;
    action: ComponentAction;
    data: LayoutRow[];
    columns: string[];
    plateFormat: string;
}

const COLORS = [
    '#2563eb', '#dc2626', '#16a34a', '#c2410c', '#7c3aed',
    '#0891b2', '#db2777', '#65a30d', '#ea580c', '#4d7c0f',
    '#92400e', '#4f46e5', '#9333ea', '#0f766e', '#be123c',
    '#475569', '#0284c7', '#b91c1c', '#15803d', '#a16207',
    '#6d28d9', '#0e7490', '#a21caf', '#3f6212', '#9a3412',
    '#166534', '#7f1d1d', '#1d4ed8', '#86198f', '#334155',
];

const DIMS: Record<string, [rows: string[], cols: number, size: number]> = {
    '6_well': [['A', 'B'], 3, 70],
    '12_well': [['A', 'B', 'C'], 4, 50],
    '24_well': [['A', 'B', 'C', 'D'], 6, 50],
    '48_well': [['A', 'B', 'C', 'D', 'E', 'F'], 8, 50],
    '96_well': [['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'], 12, 45],
    '384_well': [
        Array.from({ length: 16 }, (_, i) => String.fromCharCode(65 + i)),
        24,
        30,
    ],
    '1536_well': [
        [
            ...Array.from({ length: 26 }, (_, i) => String.fromCharCode(65 + i)),
            'AA', 'AB', 'AC', 'AD', 'AE', 'AF',
        ],
        48,
        20,
    ],
};

const plateDims = (fmt: string) => DIMS[fmt] ?? DIMS['96_well'];
const wellRows = (fmt: string) => plateDims(fmt)[0];
const wellCols = (fmt: string) => plateDims(fmt)[1];
const cellSize = (fmt: string) => plateDims(fmt)[2];

function cx(...classes: Array<string | false | null | undefined>): string {
    return classes.filter(Boolean).join(' ');
}

function uniq(vals: Array<string | undefined>): string[] {
    return [
        ...new Set(
            vals
                .map(v => (v ?? '').toString())
                .filter(v => v.trim() !== ''),
        ),
    ];
}

function normalize(data: LayoutRow[], columns: string[], format: string): LayoutRow[] {
    const inputCols = columns.map(col => col.trim()).filter(Boolean);
    const cols = inputCols.includes('well_loc') ? [...inputCols] : ['well_loc', ...inputCols];
    const validWells = new Set<string>();

    for (const r of wellRows(format)) {
        for (let c = 1; c <= wellCols(format); c++) {
            validWells.add(`${r}${c}`);
        }
    }

    const byWell = new Map<string, LayoutRow>(
        (data ?? [])
            .map(row => {
                const cleanRow = Object.fromEntries(
                    Object.entries(row).map(([key, value]) => [
                        key.trim(),
                        (value ?? '').toString().trim(),
                    ]),
                ) as LayoutRow;
                const loc = (cleanRow.well_loc ?? '').toUpperCase();
                return [loc, { ...cleanRow, well_loc: loc }] as [string, LayoutRow];
            })
            .filter(([loc]) => validWells.has(loc)),
    );

    for (const r of wellRows(format)) {
        for (let c = 1; c <= wellCols(format); c++) {
            const loc = `${r}${c}`;
            if (!byWell.has(loc)) {
                const row: LayoutRow = Object.fromEntries(cols.map(col => [col, '']));
                row.well_loc = loc;
                byWell.set(loc, row);
            }
        }
    }

    return [...byWell.values()].map(row => {
        const out: LayoutRow = Object.fromEntries(
            cols.map(col => [col, (row[col] ?? '').toString().trim()]),
        );

        for (const col of Object.keys(row)) {
            if (!(col in out)) {
                out[col] = (row[col] ?? '').toString().trim();
            }
        }

        return out;
    });
}

function makeMap(data: LayoutRow[]): Map<string, LayoutRow> {
    return new Map(data.map(row => [(row.well_loc ?? '').toUpperCase(), row]));
}

function clone<T>(v: T): T {
    return JSON.parse(JSON.stringify(v));
}

function sameSnapshot(
    leftData: LayoutRow[],
    leftColumns: string[],
    rightData: LayoutRow[],
    rightColumns: string[],
): boolean {
    return JSON.stringify({ columns: leftColumns, data: leftData })
        === JSON.stringify({ columns: rightColumns, data: rightData });
}

type Mode = 'layout_preview' | 'layout_editor';

interface AppState {
    mode: Mode;
    data: LayoutRow[];
    columns: string[];
    plateFormat: string;
    selectedColumn: string;
    selectedValue: string;
    selectedColumnValue: string;
    extraValues: Record<string, string[]>;
    valueOrder: Record<string, string[]>;
    deleteColumnsMode: boolean;
    pendingDeleteColumn: string;
    draft: LayoutRow[] | null;
    initial: LayoutRow[] | null;
    initialColumns: string[] | null;
    initialDirty: boolean;
    dirty: boolean;
}

interface DragState {
    op: 'set' | 'clear';
    base: LayoutRow[];
    path: string[];
}

function columnValueKey(col: string, value: string): string {
    return `${col}-${value}`;
}

function selectColumnValue(s: AppState, col: string, value: string): void {
    s.selectedColumn = col;
    s.selectedValue = value;
    s.selectedColumnValue = value ? columnValueKey(col, value) : '';
}

function selectColumn(s: AppState, col: string): void {
    s.selectedColumn = col;
    s.selectedValue = '';
    s.selectedColumnValue = '';
}

function mergeValueOrder(
    current: string[],
    discovered: string[],
    extra: string[] = [],
): string[] {
    const available = new Set([...discovered, ...extra]);
    const ordered = current.filter(value => available.has(value));

    for (const value of [...discovered, ...extra]) {
        if (value && !ordered.includes(value)) {
            ordered.push(value);
        }
    }

    return ordered;
}

export function LayoutPreviewEditor(props: LayoutPreviewEditorProps) {
    const st = useRef<AppState>({
        mode: props.initialMode ?? 'layout_preview',
        data: [],
        columns: [],
        plateFormat: '96_well',
        selectedColumn: '',
        selectedValue: '',
        selectedColumnValue: '',
        extraValues: {},
        valueOrder: {},
        deleteColumnsMode: false,
        pendingDeleteColumn: '',
        draft: null,
        initial: null,
        initialColumns: null,
        initialDirty: false,
        dirty: false,
    });

    const drag = useRef<DragState | null>(null);
    const argsRef = useRef<LayoutPreviewEditorProps>(props);
    const pendingApplyRef = useRef<{
        data: LayoutRow[];
        columns: string[];
        plateFormat: string;
    } | null>(null);
    const newColRef = useRef<HTMLInputElement>(null);
    const newValueRefs = useRef<Record<string, HTMLInputElement | null>>({});

    const [, setTick] = useState(0);

    const repaint = useCallback((doHeight = true) => {
        setTick(n => n + 1);

        if (doHeight) {
            setTimeout(
                () => window.parent.postMessage(
                    {
                        isStreamlitMessage: true,
                        type: 'streamlit:setFrameHeight',
                        height: document.body.scrollHeight,
                    },
                    '*',
                ),
                50,
            );
        }
    }, []);

    const post = useCallback((type: string, extra: Record<string, unknown> = {}) => {
        window.parent.postMessage(
            {
                isStreamlitMessage: true,
                type,
                ...extra,
            },
            '*',
        );
    }, []);

    const pushValue = useCallback((value: ComponentValue) => {
        post('streamlit:setComponentValue', { value, dataType: 'json' });
    }, [post]);

    const componentValue = (
        s: AppState,
        action: ComponentAction,
        data: LayoutRow[],
    ): ComponentValue => ({
        mode: s.mode,
        action,
        data,
        columns: [...s.columns],
        plateFormat: s.plateFormat,
    });

    const syncArgs = useCallback((next: LayoutPreviewEditorProps) => {
        argsRef.current = next;

        const s = st.current;

        const incomingFormat = next.plateFormat ?? s.plateFormat ?? '96_well';
        const columns = next.columns ?? Object.keys((next.layoutData ?? [])[0] ?? { well_loc: '' });
        const incomingColumns = columns.includes('well_loc') ? columns : ['well_loc', ...columns];
        const incomingData = normalize(next.layoutData ?? [], incomingColumns, incomingFormat);
        const pendingApply = pendingApplyRef.current;

        if (pendingApply) {
            const pendingData = normalize(
                pendingApply.data,
                pendingApply.columns,
                pendingApply.plateFormat,
            );

            if (!sameSnapshot(incomingData, incomingColumns, pendingData, pendingApply.columns)) {
                return;
            }

            pendingApplyRef.current = null;
        }

        const hasLoadedData = s.data.length > 0;
        if (s.mode === 'layout_editor' && hasLoadedData) {
            if (incomingFormat !== s.plateFormat) {
                s.plateFormat = incomingFormat;
                s.data = normalize(s.data, s.columns, incomingFormat);
                s.draft = normalize(s.draft ?? s.data, s.columns, incomingFormat);
                s.dirty = true;
            }
            return;
        }
        if (s.dirty) {
            return;
        }

        const format = incomingFormat;

        s.plateFormat = format;
        s.columns = incomingColumns;
        s.data = incomingData;

        const editable = s.columns.filter(c => c !== 'well_loc');

        s.valueOrder = Object.fromEntries(
            editable.map(col => [
                col,
                mergeValueOrder(
                    s.valueOrder[col] ?? [],
                    uniq(s.data.map(row => row[col])),
                    s.extraValues[col] ?? [],
                ),
            ]),
        );

        let selectedColumn = s.selectedColumn;

        if (!editable.includes(selectedColumn)) {
            selectedColumn = editable.includes('type') ? 'type' : editable[0] ?? '';
        }

        const vals = s.valueOrder[selectedColumn] ?? [];
        let selectedValue = s.selectedValue;

        if (!vals.includes(selectedValue)) {
            selectedValue = vals[0] ?? '';
        }
        selectColumnValue(s, selectedColumn, selectedValue);

        if (next.initialMode === 'layout_editor' && (s.mode !== 'layout_editor' || !s.draft)) {
            s.mode = 'layout_editor';
            s.deleteColumnsMode = false;
            s.pendingDeleteColumn = '';
            s.initial = clone(s.data);
            s.initialColumns = [...s.columns];
            s.initialDirty = s.dirty;
            s.draft = clone(s.data);
        }

        s.extraValues = Object.fromEntries(
            Object.entries(s.extraValues).filter(([col]) => editable.includes(col)),
        );
    }, []);

    useEffect(() => {
        const onMsg = (evt: MessageEvent) => {
            if (evt.data?.type === 'streamlit:render') {
                syncArgs((evt.data.args ?? {}) as LayoutPreviewEditorProps);
                repaint();
            }
        };
        const onResize = () => repaint();

        window.addEventListener('message', onMsg);
        window.addEventListener('resize', onResize);
        const resizeObserver = new ResizeObserver(() => repaint());
        resizeObserver.observe(document.body);

        syncArgs(props);
        post('streamlit:componentReady', { apiVersion: 1 });
        repaint();

        return () => {
            window.removeEventListener('message', onMsg);
            window.removeEventListener('resize', onResize);
            resizeObserver.disconnect();
        };
    }, []); // eslint-disable-line react-hooks/exhaustive-deps

    const cur = (): LayoutRow[] =>
        st.current.mode === 'layout_editor' && st.current.draft
            ? st.current.draft
            : st.current.data;

    const addColumn = (name: string) => {
        const s = st.current;
        const col = name.trim();

        if (!col || col === 'well_loc' || s.columns.includes(col)) {
            return;
        }

        s.columns.push(col);
        s.data.forEach(r => {
            r[col] = '';
        });
        s.draft?.forEach(r => {
            r[col] = '';
        });

        selectColumnValue(s, col, '');
        s.extraValues[col] = [];
        s.valueOrder[col] = [];
        s.dirty = true;
        repaint();
    };

    const addValue = (col: string, value: string) => {
        const v = value.trim();

        if (!v) {
            return;
        }

        const existing = uniq([
            ...cur().map(row => row[col]),
            ...(st.current.extraValues[col] ?? []),
        ]);

        if (!existing.includes(v)) {
            st.current.extraValues[col] = [...(st.current.extraValues[col] ?? []), v];
        }

        st.current.valueOrder[col] = mergeValueOrder(
            st.current.valueOrder[col] ?? [],
            uniq(cur().map(row => row[col])),
            [...(st.current.extraValues[col] ?? []), v],
        );
        selectColumnValue(st.current, col, v);
        repaint();
    };

    const deleteColumn = (col: string) => {
        const s = st.current;

        if (col === 'well_loc') {
            return;
        }

        const target = s.mode === 'layout_editor' && s.draft ? s.draft : s.data;

        s.columns = s.columns.filter(c => c !== col);
        target.forEach(row => {
            delete row[col];
        });
        delete s.extraValues[col];
        delete s.valueOrder[col];
        delete newValueRefs.current[col];

        const editable = s.columns.filter(c => c !== 'well_loc');

        if (s.selectedColumn === col || !editable.includes(s.selectedColumn)) {
            const selectedColumn = editable.includes('type') ? 'type' : editable[0] ?? '';
            const selectedValue = selectedColumn
                ? s.valueOrder[selectedColumn]?.[0] ?? ''
                : '';
            selectColumnValue(s, selectedColumn, selectedValue);
        }

        if (!editable.length) {
            s.deleteColumnsMode = false;
        }
        if (s.pendingDeleteColumn === col) {
            s.pendingDeleteColumn = '';
        }

        s.dirty = true;
        repaint();
    };

    const requestDeleteColumn = (col: string) => {
        const s = st.current;
        const hasValues = cur().some(row => (row[col] ?? '').trim() !== '');

        if (!hasValues) {
            deleteColumn(col);
            return;
        }

        drag.current = null;
        selectColumn(s, col);
        s.pendingDeleteColumn = col;
        repaint();
    };

    const enterEdit = () => {
        const s = st.current;

        s.mode = 'layout_editor';
        s.deleteColumnsMode = false;
        s.pendingDeleteColumn = '';
        s.initial = clone(s.data);
        s.initialColumns = [...s.columns];
        s.initialDirty = s.dirty;
        s.draft = clone(s.data);

        pushValue(componentValue(s, 'lock', s.data));
        repaint();
    };

    const cancelEdit = () => {
        const s = st.current;

        s.draft = clone(s.initial ?? s.data);
        s.data = clone(s.draft);
        s.columns = [...(s.initialColumns ?? s.columns)];
        s.dirty = s.initialDirty;
        s.deleteColumnsMode = false;
        s.pendingDeleteColumn = '';
        s.mode = 'layout_preview';

        pushValue(componentValue(s, 'cancel', s.data));
        repaint();
    };

    const leavePreview = () => {
        const s = st.current;

        s.mode = 'layout_preview';
        s.deleteColumnsMode = false;
        s.pendingDeleteColumn = '';
        s.draft = null;
        s.initial = null;
        s.initialColumns = null;
        s.initialDirty = s.dirty;

        repaint();
    };

    const commitDraft = () => {
        st.current.data = clone(st.current.draft!);
        st.current.dirty = true;
        repaint();
    };

    const applyChanges = () => {
        const s = st.current;
        const appliedData = clone(cur());
        const appliedColumns = [...s.columns];
        const appliedPlateFormat = s.plateFormat;

        s.data = appliedData;
        s.mode = 'layout_preview';
        s.deleteColumnsMode = false;
        s.pendingDeleteColumn = '';
        s.draft = null;
        s.initial = null;
        s.initialColumns = null;
        s.initialDirty = false;
        s.dirty = false;

        pendingApplyRef.current = {
            data: clone(appliedData),
            columns: appliedColumns,
            plateFormat: appliedPlateFormat,
        };
        pushValue(componentValue(s, 'apply', appliedData));
        repaint();
    };

    const paint = (loc: string) => {
        const d = drag.current;
        const s = st.current;

        if (!d || !s.draft || s.deleteColumnsMode) {
            return;
        }

        if (!d.path.includes(loc)) {
            d.path.push(loc);
        }

        let row = s.draft.find(r => (r.well_loc ?? '').toUpperCase() === loc);

        if (!row) {
            row = Object.fromEntries(s.columns.map(c => [c, ''])) as LayoutRow;
            row.well_loc = loc;
            s.draft.push(row);
        }

        row[s.selectedColumn] = d.op === 'set' ? s.selectedValue : '';
        repaint(false);
    };

    const onDragStart = (loc: string) => {
        if (st.current.deleteColumnsMode) {
            drag.current = null;
            return;
        }

        const data = cur();
        const val = makeMap(data).get(loc)?.[st.current.selectedColumn] ?? '';

        drag.current = {
            op: columnValueKey(st.current.selectedColumn, val) === st.current.selectedColumnValue ? 'clear' : 'set',
            base: clone(data),
            path: [],
        };

        paint(loc);
    };

    const onDragMove = (loc: string) => {
        const d = drag.current;
        const s = st.current;

        if (!d) {
            return;
        }

        const idx = d.path.indexOf(loc);

        if (idx >= 0) {
            const keep = d.path.slice(0, idx + 1);
            s.draft = clone(d.base);
            d.path = [];
            keep.forEach(w => paint(w));
            return;
        }

        paint(loc);
    };

    const onDragEnd = () => {
        if (drag.current) {
            drag.current = null;
            commitDraft();
        }
    };

    const updateDataCell = (rowIndex: number, col: string, value: string) => {
        const s = st.current;

        if (s.mode !== 'layout_editor') {
            return;
        }
        if (!s.draft) {
            s.draft = clone(s.data);
        }

        const sourceRow = cur()[rowIndex];
        const sourceWell = (sourceRow?.well_loc ?? '').toUpperCase();
        let row = sourceWell
            ? s.draft.find(r => (r.well_loc ?? '').toUpperCase() === sourceWell)
            : s.draft[rowIndex];

        if (!row) {
            row = Object.fromEntries(s.columns.map(c => [c, ''])) as LayoutRow;
            if (sourceWell) {
                row.well_loc = sourceWell;
            }
            s.draft.push(row);
        }

        row[col] = value;
        s.data = clone(s.draft);
        s.dirty = true;
        drag.current = null;
        repaint();
    };

    const s = st.current;
    const data = cur();
    const editable = s.columns.filter(c => c !== 'well_loc');
    for (const col of editable) {
        s.valueOrder[col] = mergeValueOrder(
            s.valueOrder[col] ?? [],
            uniq(data.map(row => row[col])),
            s.extraValues[col] ?? [],
        );
    }
    const columnValues = editable.map(col => ({
        col,
        values: s.valueOrder[col] ?? [],
    }));
    const colorMaps = new Map(
        columnValues.map(({ col, values: colValues }) => [
            col,
            new Map(colValues.map((v, i) => [v, COLORS[i % COLORS.length]])),
        ]),
    );
    const colorMap = colorMaps.get(s.selectedColumn) ?? new Map<string, string>();
    const dataColumnLengths = new Map(
        s.columns.map(col => [
            col,
            Math.max(
                col.length,
                ...data.map(row => (row[col] ?? '').length),
            ),
        ]),
    );
    const wellMap = makeMap(data);
    const size = cellSize(s.plateFormat);
    const plateWidth = (wellCols(s.plateFormat) + 1) * size;
    const dotPx = Math.max(10, size / 1.7);
    const isEditor = s.mode === 'layout_editor';
    const isDeleteMode = isEditor && s.deleteColumnsMode;

    const cellVars = {
        '--cell-size': `${size}px`,
    } as React.CSSProperties;

    const plateVars = {
        '--plate-height': `${(wellRows(s.plateFormat).length + 1) * size}px`,
        '--plate-width': `${plateWidth}px`,
    } as React.CSSProperties;

    const dotVars = (bg: string) => ({
        '--dot-size': `${dotPx}px`,
        '--dot-bg': bg,
    }) as React.CSSProperties;

    const dotVarsForWell = (loc: string) => {
        const val = wellMap.get(loc)?.[s.selectedColumn] ?? '';
        const opacity = !isDeleteMode && s.selectedColumnValue && val && columnValueKey(s.selectedColumn, val) !== s.selectedColumnValue ? 0.42 : 1;

        return {
            ...dotVars(colorMap.get(val) ?? '#d9dde3'),
            '--dot-opacity': opacity,
        } as React.CSSProperties;
    };

    const valueButtonVars = (col: string, value: string, active: boolean) => {
        const color = colorMaps.get(col)?.get(value) ?? '#d1d5db';

        return {
            '--value-color': color,
            '--value-opacity': !isDeleteMode && s.selectedColumnValue && !active ? 0.62 : 1,
        } as React.CSSProperties;
    };

    return (
        <div
            className={cx(
                'lpe-root',
                argsRef.current.showFullDataTable && 'lpe-root-standalone',
            )}
            onMouseUp={onDragEnd}
        >
            <div className="lpe-card">
                <div className="lpe-toolbar">
                    {isEditor ? (
                        <>
                            <button
                                onClick={cancelEdit}
                                className="lpe-button lpe-button-danger"
                            >
                                Cancel
                            </button>

                            <button
                                onClick={applyChanges}
                                disabled={!s.dirty}
                                className={cx(
                                    'lpe-button',
                                    'lpe-button-primary',
                                    !s.dirty && 'lpe-button-disabled',
                                )}
                            >
                                Apply changes
                            </button>
                        </>
                    ) : (
                        <button
                            onClick={enterEdit}
                            className="lpe-button lpe-button-primary"
                        >
                            Edit layout
                        </button>)}

                </div>

                <div
                    className={cx(
                        'lpe-main',
                        isEditor ? 'lpe-main-editor' : 'lpe-main-preview',
                    )}
                    style={plateVars}
                >
                    <div className="lpe-plate-wrapper">
                        <table className="lpe-plate-table">
                            <thead>
                                <tr>
                                    <th className="lpe-cell" style={cellVars} />
                                    {Array.from({ length: wellCols(s.plateFormat) }, (_, i) => (
                                        <th key={i} className="lpe-cell" style={cellVars}>
                                            {i + 1}
                                        </th>
                                    ))}
                                </tr>
                            </thead>

                            <tbody>
                                {wellRows(s.plateFormat).map(rowName => (
                                    <tr key={rowName}>
                                        <th className="lpe-cell" style={cellVars}>
                                            {rowName}
                                        </th>

                                        {Array.from({ length: wellCols(s.plateFormat) }, (_, ci) => {
                                            const loc = `${rowName}${ci + 1}`;
                                            const val = wellMap.get(loc)?.[s.selectedColumn] ?? '';

                                            return (
                                                <td key={ci} className="lpe-cell" style={cellVars}>
                                                    <span
                                                        className={cx(
                                                            'lpe-dot',
                                                            isEditor && !isDeleteMode ? 'lpe-dot-editable' : 'lpe-dot-readonly',
                                                        )}
                                                        style={dotVarsForWell(loc)}
                                                        title={`${loc} ${s.selectedColumn}: ${val || 'blank'}`}
                                                        onMouseDown={
                                                            isEditor && !isDeleteMode
                                                                ? e => {
                                                                    e.preventDefault();
                                                                    onDragStart(loc);
                                                                }
                                                                : undefined
                                                        }
                                                        onMouseEnter={isEditor && !isDeleteMode ? () => onDragMove(loc) : undefined}
                                                    />
                                                </td>
                                            );
                                        })}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>

                    <div className="lpe-side-panel">
                        <div className="lpe-column-grid">
                            {columnValues.map(({ col, values: colValues }) => (
                                <div
                                    key={col}
                                    className={cx(
                                        'lpe-value-column',
                                        (
                                            isDeleteMode
                                                ? s.pendingDeleteColumn === col
                                                : s.selectedColumn === col
                                        ) && 'lpe-value-column-active',
                                    )}
                                >
                                    {isDeleteMode ? (
                                        <>
                                            <button
                                                type="button"
                                                className="lpe-column-heading lpe-column-delete-button"
                                                onClick={() => requestDeleteColumn(col)}
                                                title={`Delete ${col}`}
                                            >
                                                {col}
                                            </button>
                                            {s.pendingDeleteColumn === col && (
                                                <div className="lpe-delete-confirm">
                                                    <div>
                                                        This column has values present in the layout. Are you sure you want to delete it and all its contents?
                                                    </div>
                                                    <div className="lpe-delete-confirm-actions">
                                                        <button
                                                            type="button"
                                                            className="lpe-button lpe-button-danger"
                                                            onClick={() => deleteColumn(col)}
                                                        >
                                                            Yes, delete
                                                        </button>
                                                        <button
                                                            type="button"
                                                            className="lpe-button"
                                                            onClick={() => {
                                                                s.pendingDeleteColumn = '';
                                                                repaint();
                                                            }}
                                                        >
                                                            No, cancel
                                                        </button>
                                                    </div>
                                                </div>
                                            )}
                                        </>
                                    ) : (
                                        <button
                                            type="button"
                                            className="lpe-column-heading lpe-column-heading-button"
                                            title={col}
                                            onClick={() => {
                                                selectColumn(s, col);
                                                repaint();
                                            }}
                                        >
                                            {col}
                                        </button>
                                    )}

                                    <div className="lpe-value-list">
                                        {colValues.map(value => (
                                            (() => {
                                                const active = !isDeleteMode && s.selectedColumnValue === columnValueKey(col, value);

                                                return (
                                                    <button
                                                        key={value}
                                                        type="button"
                                                        className={cx(
                                                            'lpe-value-button',
                                                            active && 'lpe-value-button-active',
                                                        )}
                                                        style={valueButtonVars(col, value, active)}
                                                        disabled={isDeleteMode}
                                                        onClick={() => {
                                                            if (isDeleteMode) {
                                                                return;
                                                            }
                                                            selectColumnValue(s, col, value);
                                                            repaint();
                                                        }}
                                                        title={`${col}: ${value}`}
                                                    >
                                                        {value}
                                                    </button>
                                                );
                                            })()
                                        ))}
                                    </div>

                                    {isEditor && !s.deleteColumnsMode && (
                                        <div className="lpe-add-value-row">
                                            <input
                                                ref={el => {
                                                    newValueRefs.current[col] = el;
                                                }}
                                                placeholder="Add value"
                                                aria-label={`Add value to ${col}`}
                                                className="lpe-input lpe-add-value-input"
                                                onKeyDown={e => {
                                                    if (e.key === 'Enter') {
                                                        addValue(col, newValueRefs.current[col]?.value ?? '');
                                                        if (newValueRefs.current[col]) {
                                                            newValueRefs.current[col]!.value = '';
                                                        }
                                                    }
                                                }}
                                            />

                                            <button
                                                type="button"
                                                className="lpe-button lpe-add-value-button"
                                                title={`Add value to ${col}`}
                                                onClick={() => {
                                                    addValue(col, newValueRefs.current[col]?.value ?? '');
                                                    if (newValueRefs.current[col]) {
                                                        newValueRefs.current[col]!.value = '';
                                                    }
                                                }}
                                            >
                                                +
                                            </button>
                                        </div>
                                    )}
                                </div>
                            ))}

                            {isEditor && (
                                <div className="lpe-value-column lpe-add-column-column">
                                    {!s.deleteColumnsMode &&
                                        <div className="lpe-add-column-row">
                                            <input
                                                ref={newColRef}
                                                placeholder="Add column"
                                                aria-label="Add column"
                                                className="lpe-input lpe-add-column-input"
                                                disabled={s.deleteColumnsMode}
                                                onKeyDown={e => {
                                                    if (e.key === 'Enter') {
                                                        addColumn(newColRef.current?.value ?? '');
                                                        if (newColRef.current) {
                                                            newColRef.current.value = '';
                                                        }
                                                    }
                                                }}
                                            />
                                            <button
                                                type="button"
                                                className="lpe-button lpe-add-column-button"
                                                title="Add column"
                                                disabled={s.deleteColumnsMode}
                                                onClick={() => {
                                                    addColumn(newColRef.current?.value ?? '');
                                                    if (newColRef.current) {
                                                        newColRef.current.value = '';
                                                    }
                                                }}
                                            >
                                                +
                                            </button>
                                        </div>
                                    }
                                    <button
                                        type="button"
                                        onClick={() => {
                                            s.deleteColumnsMode = !s.deleteColumnsMode;
                                            s.pendingDeleteColumn = '';
                                            repaint();
                                        }}
                                        className={cx(
                                            'lpe-button',
                                            !s.deleteColumnsMode && 'lpe-button-danger',
                                            'lpe-delete-mode-button',
                                        )}
                                        disabled={!editable.length}
                                    >
                                        {s.deleteColumnsMode ? 'Cancel' : 'Delete columns'}
                                    </button>
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                <div
                    className={cx(
                        'lpe-data-wrapper',
                        argsRef.current.showFullDataTable && 'lpe-data-wrapper-full',
                    )}
                >
                    <table className="lpe-data-table">
                        <thead>
                            <tr>
                                {s.columns.map(col => (
                                    <th key={col}>{col}</th>
                                ))}
                            </tr>
                        </thead>

                        <tbody>
                            {data.map((row, ri) => (
                                <tr key={ri}>
                                    {s.columns.map(col => (
                                        <td key={col}>
                                            <input
                                                type="text"
                                                id={`lpe-cell-${ri}-${col}`}
                                                value={row[col] ?? ''}
                                                readOnly={!isEditor}
                                                onChange={
                                                    isEditor
                                                        ? e => updateDataCell(ri, col, e.target.value)
                                                        : undefined
                                                }
                                                style={{
                                                    '--cell-text-length': dataColumnLengths.get(col) ?? 1,
                                                } as React.CSSProperties}
                                                className={cx(
                                                    'lpe-cell-input',
                                                    isEditor
                                                        ? 'lpe-cell-input-editing'
                                                        : 'lpe-cell-input-preview',
                                                )}
                                            />
                                        </td>
                                    ))}
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}

const root = document.getElementById('root');

if (!root) {
    throw new Error('Missing root element');
}

ReactDOM.createRoot(root).render(
    <React.StrictMode>
        <LayoutPreviewEditor />
    </React.StrictMode>,
);
