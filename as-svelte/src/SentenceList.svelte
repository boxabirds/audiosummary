<!-- SentenceList.svelte -->
<script>
    import { createEventDispatcher } from 'svelte';

    export let processing;
    export let sentences = [];

    const dispatch = createEventDispatcher();

    function select() {
        const selectedSentences = sentences.filter(sentence => sentence.selected);
        dispatch('select', selectedSentences);
    }
</script>

<style>
    .sentence-list {
        display: flex;
        flex-direction: column;
        align-items: center;
    }

    .table {
        width: 100%;
        border-collapse: collapse;
        margin-bottom: 1rem;
    }

    .table th,
    .table td {
        padding: 0.5rem;
        text-align: left;
        border-bottom: 1px solid #ddd;
    }

    .table th {
        font-weight: bold;
    }

    .table td input[type="checkbox"] {
        margin-right: 0.5rem;
    }

    .summarize-button {
        margin-top: 1rem;
    }
</style>

<div class="sentence-list">
    <table class="table">
        <thead>
            <tr>
                <th></th>
                <th>Sentence</th>
            </tr>
        </thead>
        <tbody>
            {#each sentences as sentence}
                <tr>
                    <td>
                        <input type="checkbox" bind:checked={sentence.selected} />
                    </td>
                    <td>{sentence.text}</td>
                </tr>
            {/each}
        </tbody>
    </table>

    <div class="summarize-button">
        <button on:click={select} disabled={processing}>
            Summarize
        </button>
    </div>
</div>
