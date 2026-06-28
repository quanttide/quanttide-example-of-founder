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
    Blueprint(product_blueprint::Commands),
    #[command(subcommand)]
    Health(health::Commands),
}

fn main() {
    let cli = Cli::parse();
    match cli.cmd {
        LabCommands::Blueprint(cmd) => product_blueprint::dispatch(cmd),
        LabCommands::Health(cmd) => health::dispatch(cmd),
    }
}
