use clap::{Parser, Subcommand};

#[derive(Parser)]
#[command(name = "lab")]
struct Cli {
    #[command(subcommand)]
    cmd: LabCommands,
}

#[derive(Subcommand)]
enum LabCommands {
    #[command(subcommand)]
    Health(health::Commands),
    #[command(subcommand)]
    Cogni(cogni::Commands),
}

fn main() {
    let cli = Cli::parse();
    match cli.cmd {
        LabCommands::Health(cmd) => health::dispatch(cmd),
        LabCommands::Cogni(cmd) => cogni::dispatch(cmd),
    }
}
